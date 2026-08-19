import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import PixelTransition from './ui/PixelTransition';

export default function BootupAnimation({ onComplete }) {
  const [phase, setPhase] = useState('logo'); // logo, morph, exit

  useEffect(() => {
    const morphTimer = setTimeout(() => {
      setPhase('morph');
    }, 1000);

    const exitTimer = setTimeout(() => {
      setPhase('exit');
    }, 1600);

    const completeTimer = setTimeout(() => {
      onComplete();
    }, 2100);

    return () => {
      clearTimeout(morphTimer);
      clearTimeout(exitTimer);
      clearTimeout(completeTimer);
    };
  }, [onComplete]);

  return (
    <motion.div 
      initial={{ opacity: 1 }}
      animate={{ opacity: phase === 'exit' ? 0 : 1 }}
      transition={{ duration: 0.5 }}
      className="fixed inset-0 bg-[#001122] flex items-center justify-center overflow-hidden z-50"
    >
      <div className="relative w-96 h-96 flex items-center justify-center">
        <PixelTransition
          firstContent={
            <img 
              src="/cdg-logo.png" 
              alt="DarKnight Logo" 
              className="w-full h-full object-contain"
            />
          }
          secondContent={
            <div className="w-full h-full bg-transparent" />
          }
          gridSize={24}
          pixelColor="#001122"
          animationStepDuration={0.5}
          trigger={phase === 'morph'}
          once={true}
        />
      </div>
    </motion.div>
  );
}
