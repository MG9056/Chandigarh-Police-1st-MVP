import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

export default function BootupAnimation({ onComplete }) {
  const [phase, setPhase] = useState('logo'); // logo, morph, exit

  useEffect(() => {
    const morphTimer = setTimeout(() => {
      setPhase('morph');
    }, 2000);

    const exitTimer = setTimeout(() => {
      setPhase('exit');
    }, 3000);

    const completeTimer = setTimeout(() => {
      onComplete();
    }, 3500);

    return () => {
      clearTimeout(morphTimer);
      clearTimeout(exitTimer);
      clearTimeout(completeTimer);
    };
  }, [onComplete]);

  // Generate a solid block of 0s and 1s
  const textMorph = Array.from({ length: 400 })
    .map(() => (Math.random() > 0.5 ? '1' : '0'))
    .join('');

  return (
    <motion.div 
      initial={{ opacity: 1 }}
      animate={{ opacity: phase === 'exit' ? 0 : 1 }}
      transition={{ duration: 0.5 }}
      className="fixed inset-0 bg-[#001122] flex items-center justify-center overflow-hidden z-50"
    >
      <div className="relative w-64 h-64 flex items-center justify-center">
        {/* The Original Logo */}
        <motion.img 
          src="/cdg-logo.png" 
          alt="DarKnight Logo" 
          initial={{ opacity: 1, filter: "blur(0px)" }}
          animate={
            phase === 'morph' || phase === 'exit'
              ? { opacity: 0, filter: "blur(4px)" }
              : { opacity: 1, filter: "blur(0px)" }
          }
          transition={{ duration: 0.5 }}
          className="absolute inset-0 w-full h-full object-contain z-10"
        />

        {/* The 0s and 1s Morph target */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={
            phase === 'morph'
              ? { opacity: 1, scale: 1 }
              : phase === 'exit' ? { opacity: 0, scale: 1.1 } : { opacity: 0 }
          }
          transition={{ duration: 0.5 }}
          className="absolute inset-0 z-20 flex items-center justify-center"
        >
          <div 
            className="w-full h-full flex flex-wrap content-start items-start text-orange-500 font-mono text-[10px] leading-none overflow-hidden text-justify"
            style={{ textShadow: "0 0 8px rgba(249, 115, 22, 0.8)", wordBreak: "break-all" }}
          >
            {textMorph}
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}
