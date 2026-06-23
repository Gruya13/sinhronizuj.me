import re
import numpy as np
from datetime import datetime, timedelta
from sklearn.cluster import DBSCAN
from backend.core.config import settings
from backend.core.database import SessionLocal
from backend.core.models import Segment, Project, WikiRule
from backend.services.embedding import embedding_service
from backend.worker.utils import call_modal_endpoint
from backend.worker.translation import extract_and_parse_json

def run_nightly_pattern_analysis():
    """
    Ekstrahuje loše prevode iz poslednja 24 sata, klasteruje ih
    i generiše Wiki pravila za prevenciju ponovljenih grešaka.
    """
    print("[BETA] Započinjem noćnu analizu obrazaca grešaka...", flush=True)
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=1)
        bad_segments = db.query(Segment).join(Project).filter(
            Project.created_at >= cutoff,
            Segment.qe_score < 0.85
        ).all()

        print(f"[BETA] Pronađeno loših segmenata (QE < 0.85): {len(bad_segments)}", flush=True)
        if not bad_segments:
            return {"status": "success", "new_rules_added": 0, "message": "Nema loših segmenata za analizu."}

        texts = [s.original for s in bad_segments if s.original]
        valid_segments = [s for s in bad_segments if s.original]

        embeddings = []
        filtered_segs = []
        for s in valid_segments:
            emb = embedding_service.get_embedding(s.original)
            if emb:
                embeddings.append(emb)
                filtered_segs.append(s)

        if not embeddings or len(embeddings) < 3:
            return {"status": "success", "new_rules_added": 0, "message": "Nedovoljno loših primera za klasterovanje."}

        X = np.array(embeddings)
        # DBSCAN sa kosinusnom distancom (threshold < 0.3)
        dbscan = DBSCAN(eps=0.3, min_samples=3, metric='cosine')
        labels = dbscan.fit_predict(X)

        unique_labels = set(labels)
        if -1 in unique_labels:
            unique_labels.remove(-1)

        print(f"[BETA] DBSCAN detektovao {len(unique_labels)} klastera loših prevoda.", flush=True)
        new_rules_count = 0

        for label in unique_labels:
            indices = np.where(labels == label)[0]
            cluster_segs = [filtered_segs[idx] for idx in indices]
            
            # Uzmi do 5 primera za prompt
            examples = cluster_segs[:5]
            examples_str = ""
            for idx_ex, seg in enumerate(examples):
                examples_str += f"{idx_ex+1}. Engleski: \"{seg.original}\" -> Prevedeno na srpski: \"{seg.translated}\"\n"

            prompt = (
                "Ti si Lead AI Lingvistički Inženjer za srpski jezik.\n"
                "Analiziraj sledeće primere loših prevoda i prepoznaj uobičajenu grešku (obrazac) koja se ponavlja.\n"
                "Predloži JEDNO sažeto, jasno i univerzalno gramatičko ili stilsko pravilo na srpskom jeziku (ekavica, latinica) koje ispravlja ove greške.\n"
                "Pravilo mora biti napisano u imperativu ili kao jasna instrukcija za LLM prevodioca (npr. 'Prevedi frazu \"actually\" kao \"zapravo\" ili \"u stvari\", a ne kao \"stvarno\".').\n\n"
                "PRIMERI LOŠIH PREVODA:\n"
                f"{examples_str}\n"
                "ODGOVOR FORMAT:\n"
                "Odgovori isključivo u sledećem JSON formatu, bez ikakvog dodatnog teksta, objašnjenja ili think tagova:\n"
                "{\n"
                "  \"rule_text\": \"tekst pravila na srpskom\",\n"
                "  \"category\": \"general\"\n"
                "}\n"
            )

            if not settings.MODAL_TRANSLATOR_URL:
                print("[BETA WARNING] MODAL_TRANSLATOR_URL nije konfigurisan. Preskačem generisanje pravila.", flush=True)
                continue

            url = f"{settings.MODAL_TRANSLATOR_URL.rstrip('/')}/v1/chat/completions"
            payload = {
                "model": "mistral-translator",
                "messages": [
                    {"role": "system", "content": "Ti si stručni lingvistički analizator grešaka. Vrati isključivo validan JSON prema šemi."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 1000,
                "guided_json": {
                    "type": "object",
                    "properties": {
                        "rule_text": {"type": "string"},
                        "category": {"type": "string"}
                    },
                    "required": ["rule_text", "category"]
                }
            }

            try:
                res = call_modal_endpoint(url=url, payload=payload, timeout_seconds=60)
                content = res["choices"][0]["message"]["content"].strip()
                content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL).strip()
                
                data = extract_and_parse_json(content)
                if data and data.get("rule_text"):
                    rule_text = data["rule_text"].strip()
                    category = data.get("category", "general").strip()

                    # Provera duplikata
                    exists = db.query(WikiRule).filter(
                        WikiRule.content == rule_text,
                        WikiRule.is_global == True
                    ).first()

                    if not exists:
                        new_rule = WikiRule(
                            user_id=None,
                            title=f"Auto Rule {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                            content=rule_text,
                            category=category,
                            is_global=True
                        )
                        db.add(new_rule)
                        new_rules_count += 1
                        print(f"[BETA] Uspešno dodato novo Wiki pravilo: {rule_text}", flush=True)
            except Exception as e:
                print(f"[BETA ERROR] Greška pri analizi klastera {label}: {e}", flush=True)

        db.commit()
        print(f"[BETA SUCCESS] Noćna analiza završena. Dodato novih pravila: {new_rules_count}", flush=True)
        return {"status": "success", "new_rules_added": new_rules_count}
    except Exception as e:
        db.rollback()
        print(f"[BETA ERROR] Greška u run_nightly_pattern_analysis: {e}", flush=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
