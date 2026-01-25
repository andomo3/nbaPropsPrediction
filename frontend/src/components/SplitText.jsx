import React, { useEffect, useMemo, useRef, useState } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(ScrollTrigger, useGSAP);

const SplitText = ({
    text,
    className = '',
    delay = 0,
    duration = 1,
    ease = 'power3.out',
    splitType = 'chars',
    from = { opacity: 0, y: 20 },
    to = { opacity: 1, y: 0 },
    threshold = 0.1,
    rootMargin = '-100px',
    tag = 'p',
    textAlign = 'left',
    spanClassName = '',
    onLetterAnimationComplete,
    showCallback = false,
}) => {
    const containerRef = useRef(null);
    const spansRef = useRef([]);
    const [fontsLoaded, setFontsLoaded] = useState(false);

    spansRef.current = [];

    const segments = useMemo(() => {
        if (!text) return [];
        if (splitType === 'words') {
            return text.split(' ').map((word, index, arr) =>
                index < arr.length - 1 ? `${word} ` : word
            );
        }
        return Array.from(text);
    }, [text, splitType]);

    useEffect(() => {
        if (!document?.fonts) {
            setFontsLoaded(true);
            return;
        }
        if (document.fonts.status === 'loaded') {
            setFontsLoaded(true);
            return;
        }
        document.fonts.ready.then(() => setFontsLoaded(true));
    }, []);

    useGSAP(
        () => {
            const container = containerRef.current;
            if (!container || !fontsLoaded) return;
            const letters = spansRef.current;
            if (!letters.length) return;

            const startPct = (1 - threshold) * 100;
            const marginMatch = /^(-?\d+(?:\.\d+)?)(px|em|rem|%)?$/.exec(rootMargin);
            const marginValue = marginMatch ? parseFloat(marginMatch[1]) : 0;
            const marginUnit = marginMatch ? marginMatch[2] || 'px' : 'px';
            const sign =
                marginValue === 0
                    ? ''
                    : marginValue < 0
                        ? `-=${Math.abs(marginValue)}${marginUnit}`
                        : `+=${marginValue}${marginUnit}`;
            const start = `top ${startPct}%${sign}`;

            gsap.fromTo(
                letters,
                { ...from },
                {
                    ...to,
                    duration,
                    ease,
                    stagger: delay / 1000,
                    immediateRender: false,
                    scrollTrigger: {
                        trigger: container,
                        start,
                        once: true,
                        fastScrollEnd: true,
                        anticipatePin: 0.4,
                    },
                    onComplete: () => {
                        if (showCallback && onLetterAnimationComplete) {
                            onLetterAnimationComplete();
                        }
                    },
                }
            );
        },
        {
            dependencies: [
                text,
                delay,
                duration,
                ease,
                splitType,
                JSON.stringify(from),
                JSON.stringify(to),
                threshold,
                rootMargin,
                fontsLoaded,
                showCallback,
            ],
            scope: containerRef,
        }
    );

    const content = segments.map((char, index) => (
        <span
            key={`${char}-${index}`}
            ref={(el) => el && spansRef.current.push(el)}
            className={`inline-block will-change-transform ${spanClassName}`}
        >
            {char === ' ' ? '\u00A0' : char}
        </span>
    ));

    const style = {
        textAlign,
        overflow: 'hidden',
        display: 'inline-block',
        whiteSpace: 'normal',
        wordWrap: 'break-word',
        willChange: 'transform, opacity',
    };

    switch (tag) {
        case 'h1':
            return (
                <h1 ref={containerRef} className={className} style={style}>
                    {content}
                </h1>
            );
        case 'h2':
            return (
                <h2 ref={containerRef} className={className} style={style}>
                    {content}
                </h2>
            );
        case 'h3':
            return (
                <h3 ref={containerRef} className={className} style={style}>
                    {content}
                </h3>
            );
        case 'h4':
            return (
                <h4 ref={containerRef} className={className} style={style}>
                    {content}
                </h4>
            );
        case 'h5':
            return (
                <h5 ref={containerRef} className={className} style={style}>
                    {content}
                </h5>
            );
        case 'h6':
            return (
                <h6 ref={containerRef} className={className} style={style}>
                    {content}
                </h6>
            );
        default:
            return (
                <p ref={containerRef} className={className} style={style}>
                    {content}
                </p>
            );
    }
};

export default SplitText;
