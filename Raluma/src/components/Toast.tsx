import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, XCircle, Info, X } from 'lucide-react';
import { useToastStore } from '../store/toastStore';

const CONFIG = {
  success: {
    icon: CheckCircle2,
    cls: 'bg-emerald-500/15 border-emerald-500/35 text-emerald-300',
    bar: 'bg-emerald-500',
  },
  error: {
    icon: XCircle,
    cls: 'bg-red-500/15 border-red-500/35 text-red-300',
    bar: 'bg-red-500',
  },
  info: {
    icon: Info,
    cls: 'bg-[#2a7a8a]/20 border-[#2a7a8a]/40 text-[#4fd1c5]',
    bar: 'bg-[#4fd1c5]',
  },
} as const;

export default function ToastContainer() {
  const { toasts, remove } = useToastStore();

  return (
    <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-3 pointer-events-none">
      <AnimatePresence initial={false}>
        {toasts.map(t => {
          const { icon: Icon, cls, bar } = CONFIG[t.type];
          return (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, x: 80, scale: 0.85 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 80, scale: 0.85 }}
              transition={{ type: 'spring', stiffness: 350, damping: 28 }}
              className={`pointer-events-auto relative overflow-hidden flex items-start gap-3 px-5 py-4 rounded-2xl border backdrop-blur-md shadow-2xl ${cls} min-w-[280px] max-w-[400px]`}
            >
              {/* Прогресс-бар внизу */}
              <motion.div
                className={`absolute bottom-0 left-0 h-[3px] ${bar} opacity-50`}
                initial={{ width: '100%' }}
                animate={{ width: '0%' }}
                transition={{ duration: 4.5, ease: 'linear' }}
              />
              <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <span className="flex-1 text-sm font-medium leading-snug">{t.message}</span>
              <button
                onClick={() => remove(t.id)}
                className="ml-1 opacity-50 hover:opacity-100 transition-opacity flex-shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
