import { useEffect, useState } from 'react';
import { Database, TrendingUp, Brain, Sparkles, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import logo from '../assets/perchave_final.png';

const DEFAULT_DURATION = 6000;

const loadingSteps = [
    { icon: Database, text: 'Fetching player data...' },
    { icon: TrendingUp, text: 'Calculating rolling averages...' },
    { icon: Brain, text: 'Running prediction model...' },
    { icon: Sparkles, text: 'Generating insights...' },
];

const PredictionLoading = ({ duration = DEFAULT_DURATION }) => {
    const [currentStep, setCurrentStep] = useState(0);
    const [progress, setProgress] = useState(0);
    const [startTime] = useState(Date.now());
    const stepDuration = duration / 4;

    useEffect(() => {
        const progressInterval = setInterval(() => {
            const elapsed = Date.now() - startTime;
            const newProgress = Math.min((elapsed / duration) * 100, 100);
            setProgress(newProgress);

            const newStep = Math.min(Math.floor(elapsed / stepDuration), loadingSteps.length - 1);
            if (newStep !== currentStep) {
                setCurrentStep(newStep);
            }
        }, 30);

        return () => clearInterval(progressInterval);
    }, [startTime, currentStep]);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background">
            <div className="absolute inset-0 overflow-hidden">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/5 rounded-full blur-3xl" />
            </div>

            <div className="relative w-full max-w-md mx-4 text-center">
                <div className="flex justify-center mb-8">
                    <div className="relative">
                        <div className="absolute inset-[-4px] rounded-3xl bg-primary/20 blur-xl animate-pulse" />

                        <div className="relative w-24 h-24 rounded-3xl bg-card border-2 border-primary/30 flex items-center justify-center">
                            <img src={logo} alt="PropEdge" className="h-12 w-12 object-contain" />
                        </div>

                        <div
                            className="absolute inset-[-12px] rounded-full border-2 border-transparent border-t-primary"
                            style={{ animation: 'spin 1.5s linear infinite' }}
                        />

                        <div
                            className="absolute inset-[-24px] rounded-full border border-transparent border-b-primary/30"
                            style={{ animation: 'spin 2.5s linear infinite reverse' }}
                        />

                        <div
                            className="absolute -top-1 -right-1 w-3 h-3 bg-primary rounded-full animate-ping"
                            style={{ animationDuration: '1.5s' }}
                        />
                        <div
                            className="absolute -bottom-1 -left-1 w-2 h-2 bg-primary/60 rounded-full animate-ping"
                            style={{ animationDuration: '2s', animationDelay: '0.5s' }}
                        />
                    </div>
                </div>

                <div className="mt-6 text-center">
                    <span className="text-2xl font-bold text-foreground tracking-tight">PropEdge</span>
                    <div
                        className="h-0.5 w-0 bg-primary mx-auto mt-2 animate-expand"
                        style={{ '--expand-duration': `${duration}ms` }}
                    />
                </div>
                <p className="text-muted-foreground mb-8">Analyzing your prediction</p>

                <div className="mb-8 px-4">
                    <div className="h-2 bg-secondary rounded-full overflow-hidden">
                        <div
                            className="h-full bg-primary rounded-full transition-all duration-100 ease-linear"
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                    <div className="flex justify-between mt-3 text-sm">
                        <span className="text-muted-foreground font-mono">{Math.round(progress)}%</span>
                        <span className="text-muted-foreground">
                            {((duration - (progress / 100) * duration) / 1000).toFixed(1)}s remaining
                        </span>
                    </div>
                </div>

                <div className="rounded-2xl border border-border bg-card/50 p-4">
                    <div className="space-y-2">
                        {loadingSteps.map((step, index) => {
                            const Icon = step.icon;
                            const isActive = index === currentStep;
                            const isComplete = index < currentStep;

                            return (
                                <div
                                    key={index}
                                    className={cn(
                                        'flex items-center gap-3 p-3 rounded-xl transition-all duration-300',
                                        isActive && 'bg-primary/10 border border-primary/20',
                                        isComplete && 'opacity-50',
                                        !isActive && !isComplete && 'opacity-25',
                                    )}
                                >
                                    <div
                                        className={cn(
                                            'w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-all duration-300',
                                            isActive && 'bg-primary text-primary-foreground scale-110',
                                            isComplete && 'bg-primary/20 text-primary',
                                            !isActive && !isComplete && 'bg-secondary text-muted-foreground',
                                        )}
                                    >
                                        {isComplete ? (
                                            <Check className="w-4 h-4" />
                                        ) : (
                                            <Icon className={cn('w-4 h-4', isActive && 'animate-pulse')} />
                                        )}
                                    </div>
                                    <span
                                        className={cn(
                                            'text-sm text-left transition-colors',
                                            isActive ? 'text-foreground font-medium' : 'text-muted-foreground',
                                        )}
                                    >
                                        {step.text}
                                    </span>
                                    {isActive && (
                                        <div className="ml-auto flex gap-1">
                                            <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0ms' }} />
                                            <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '150ms' }} />
                                            <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '300ms' }} />
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default PredictionLoading;
