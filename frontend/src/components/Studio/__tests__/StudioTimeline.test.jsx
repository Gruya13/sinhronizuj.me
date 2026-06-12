import { vi, describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import StudioTimeline from '../StudioTimeline';
import React from 'react';

// Mock wavesurfer.js
vi.mock('wavesurfer.js', () => ({
  default: {
    create: () => ({
      load: vi.fn().mockResolvedValue(undefined),
      destroy: vi.fn(),
      setTime: vi.fn(),
      redraw: vi.fn()
    })
  }
}));

// Mock StudioContext
vi.mock('../../../context/StudioContext', () => ({
  useStudio: () => ({
    project: {
      id: '123',
      name: 'Test Project',
      segments: [
        { id: 1, start: 0, end: 5, status: 'edited' },
        { id: 2, start: 5, end: 10, status: 'edited' }
      ]
    },
    setProject: vi.fn(),
    timelineRef: { current: null },
    handleTimelineClick: vi.fn(),
    getVideoDuration: () => 10,
    currentTime: 2,
    visualContextError: false,
    setVisualContextError: vi.fn(),
    activeAudioSource: 'original',
    setActiveAudioSource: vi.fn(),
    selectedSegmentId: 1,
    setSelectedSegmentId: vi.fn(),
    selectedSegmentIds: [1],
    setSelectedSegmentIds: vi.fn(),
    videoRef: { current: null },
    dubbedAudioRef: { current: null },
    bgAudioRef: { current: null },
    hoveredSegmentId: null,
    setHoveredSegmentId: vi.fn(),
    dubbedBuster: 0,
    saveToHistory: vi.fn(),
    handleSaveDraft: vi.fn(),
    probniAudios: {}
  })
}));

describe('StudioTimeline Component', () => {
  it('renders Timeline header correctly', () => {
    render(<StudioTimeline />);
    expect(screen.getByText(/Vremenski Editor/i)).toBeInTheDocument();
  });

  it('renders active audio buttons', () => {
    render(<StudioTimeline />);
    expect(screen.getAllByText(/Originalni ENG Vokal/i)[0]).toBeInTheDocument();
    expect(screen.getAllByText(/Srpski glas/i)[0]).toBeInTheDocument();
  });

  it('renders segments list', () => {
    render(<StudioTimeline />);
    expect(screen.getByText('#1')).toBeInTheDocument();
    expect(screen.getByText('#2')).toBeInTheDocument();
  });
});
