export const animationKeyframes = {
  'fade-in': {
    from: { opacity: '0', transform: 'translateY(4px)' },
    to: { opacity: '1', transform: 'translateY(0)' },
  },
  'fade-in-up': {
    from: { opacity: '0', transform: 'translateY(12px)' },
    to: { opacity: '1', transform: 'translateY(0)' },
  },
  'scale-in': {
    from: { opacity: '0', transform: 'scale(0.95)' },
    to: { opacity: '1', transform: 'scale(1)' },
  },
} as const;

export const animationDurations = {
  'fade-in': 'fade-in 0.2s ease-out',
  'fade-in-up': 'fade-in-up 0.3s ease-out',
  'scale-in': 'scale-in 0.2s ease-out',
} as const;
