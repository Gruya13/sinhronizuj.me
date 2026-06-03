import os
import sys

# Dodajemo koren projekta u sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from backend.core.database import engine, Base
from backend.core.models import User, Project, Segment, Glossary

print("Ispuštam sve postojeće tabele...")
Base.metadata.drop_all(bind=engine)
print("Kreiram nove tabele sa ažuriranom šemom...")
Base.metadata.create_all(bind=engine)
print("Baza podataka je uspešno resetovana!")
