import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

const usePrefersReducedMotion = () => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
};

export const FadeIn = ({ children, delay = 0, className, direction = 'up' }) => {
    const [isVisible, setIsVisible] = useState(false);
    const prefersReducedMotion = usePrefersReducedMotion();

    useEffect(() => {
        if (prefersReducedMotion) return;
        const timer = setTimeout(() => setIsVisible(true), 50 + delay);
        return () => clearTimeout(timer);
    }, [delay, prefersReducedMotion]);

    if (prefersReducedMotion) {
        return <div className={className}>{children}</div>;
    }

    const directionClasses = {
        up: isVisible ? 'translate-y-0' : 'translate-y-6',
        down: isVisible ? 'translate-y-0' : '-translate-y-6',
        left: isVisible ? 'translate-x-0' : 'translate-x-6',
        right: isVisible ? 'translate-x-0' : '-translate-x-6',
        none: '',
    };

    return (
        <div
            className={cn(
                'transition-all duration-700 ease-out',
                isVisible ? 'opacity-100' : 'opacity-0',
                directionClasses[direction],
                className,
            )}
        >
            {children}
        </div>
    );
};

export const PageTransition = ({ children, className }) => {
    const [isVisible, setIsVisible] = useState(false);
    const prefersReducedMotion = usePrefersReducedMotion();

    useEffect(() => {
        if (prefersReducedMotion) return;
        const timer = setTimeout(() => setIsVisible(true), 50);
        return () => clearTimeout(timer);
    }, [prefersReducedMotion]);

    if (prefersReducedMotion) {
        return <div className={className}>{children}</div>;
    }

    return (
        <div
            className={cn(
                'transition-all duration-500 ease-out',
                isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4',
                className,
            )}
        >
            {children}
        </div>
    );
};

export const StaggerChildren = ({ children, className, staggerDelay = 100 }) => {
    const [isVisible, setIsVisible] = useState(false);
    const prefersReducedMotion = usePrefersReducedMotion();

    useEffect(() => {
        if (prefersReducedMotion) return;
        const timer = setTimeout(() => setIsVisible(true), 50);
        return () => clearTimeout(timer);
    }, [prefersReducedMotion]);

    if (prefersReducedMotion) {
        return <div className={className}>{children}</div>;
    }

    return (
        <div className={className}>
            {Array.isArray(children)
                ? children.map((child, index) => (
                      <div
                          key={index}
                          className={cn(
                              'transition-all duration-500 ease-out',
                              isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4',
                          )}
                          style={{
                              transitionDelay: isVisible ? `${index * staggerDelay}ms` : '0ms',
                          }}
                      >
                          {child}
                      </div>
                  ))
                : children}
        </div>
    );
};
