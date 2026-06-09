import { vi, describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Knob from '../Knob';
import React from 'react';

describe('Knob Component', () => {
  it('renders correctly with label and initial value', () => {
    render(
      <Knob
        label="Volume"
        value={5}
        min={-20}
        max={20}
        unit="dB"
        onChange={vi.fn()}
      />
    );

    expect(screen.getByText('Volume')).toBeInTheDocument();
    expect(screen.getByText('+5 dB')).toBeInTheDocument();
  });

  it('triggers onChange during drag interaction', () => {
    const onChangeMock = vi.fn();
    render(
      <Knob
        label="Volume"
        value={0}
        min={-20}
        max={20}
        step={1}
        unit="dB"
        onChange={onChangeMock}
      />
    );

    const knobCircle = screen.getByTestId('knob-circle');

    // 1. Pritisni taster miša na poziciji Y = 100
    fireEvent.mouseDown(knobCircle, { clientY: 100 });

    // 2. Prevuci miša nagore na poziciju Y = 50 (razlika 50px)
    // Sa opsegom od 40 (-20 do 20) i osetljivošću od 150px:
    // deltaVal = (50 / 150) * 40 = 13.33 -> zaokruženo na korak 1 je 13.
    fireEvent.mouseMove(document, { clientY: 50 });

    expect(onChangeMock).toHaveBeenCalledWith(13);
  });

  it('triggers onRelease on mouse up', () => {
    const onReleaseMock = vi.fn();
    render(
      <Knob
        label="Volume"
        value={0}
        min={-20}
        max={20}
        step={1}
        unit="dB"
        onChange={vi.fn()}
        onRelease={onReleaseMock}
      />
    );

    const knobCircle = screen.getByTestId('knob-circle');

    // Mousedown pa Mouseup
    fireEvent.mouseDown(knobCircle, { clientY: 100 });
    fireEvent.mouseUp(document);

    expect(onReleaseMock).toHaveBeenCalledTimes(1);
  });

  it('resets to default value on double click', () => {
    const onChangeMock = vi.fn();
    render(
      <Knob
        label="Volume"
        value={10}
        min={-20}
        max={20}
        defaultValue={0}
        unit="dB"
        onChange={onChangeMock}
      />
    );

    const knobCircle = screen.getByTestId('knob-circle');

    // Dvoklik
    fireEvent.doubleClick(knobCircle);

    expect(onChangeMock).toHaveBeenCalledWith(0);
  });
});
