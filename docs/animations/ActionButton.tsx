import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { Loader2 } from 'lucide-react';

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  loading?: boolean;
};

export function ActionButton({ loading, children, ...rest }: Props) {
  const reduce = useReducedMotion();
  const anim = reduce ? {} : { whileHover: { scale: 1.02 }, whileTap: { scale: 0.97 } };
  return (
    <motion.button
      {...anim}
      transition={{ type: 'spring', stiffness: 400, damping: 17 }}
      className="px-4 py-2 bg-primary text-primary-foreground rounded-md transition-colors duration-150 hover:bg-primary/90 motion-reduce:transform-none"
      disabled={loading}
      {...rest}
    >
      <AnimatePresence mode="wait">
        {loading ? (
          <motion.span
            key="loading"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="flex items-center gap-2"
          >
            <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" />
            Saving...
          </motion.span>
        ) : (
          <motion.span
            key="idle"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
          >
            {children}
          </motion.span>
        )}
      </AnimatePresence>
    </motion.button>
  );
}
