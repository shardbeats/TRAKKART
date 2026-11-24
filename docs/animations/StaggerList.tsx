import { motion, useReducedMotion } from 'framer-motion';

const list = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05 } },
};

const row = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
};

export function StaggerList({ items }: { items: { id: string; name: string }[] }) {
  const reduce = useReducedMotion();
  if (reduce) return <ul>{items.map((i) => <li key={i.id}>{i.name}</li>)}</ul>;
  return (
    <motion.ul variants={list} initial="hidden" animate="show">
      {items.map((i) => (
        <motion.li
          key={i.id}
          variants={row}
          transition={{ duration: 0.2, ease: 'easeOut' }}
        >
          {i.name}
        </motion.li>
      ))}
    </motion.ul>
  );
}
