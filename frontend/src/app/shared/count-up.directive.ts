import { Directive, ElementRef, Input, NgZone, OnChanges, OnDestroy } from '@angular/core';
import { animate } from 'motion';

/**
 * Animates a numeric value on the host element's text content.
 * Runs outside the Angular zone and respects prefers-reduced-motion.
 * Pair with `font-variant-numeric: tabular-nums` so digits don't jitter.
 */
@Directive({
  selector: '[mmCountUp]',
  standalone: true
})
export class CountUpDirective implements OnChanges, OnDestroy {
  @Input({ alias: 'mmCountUp', required: true }) value: number | null | undefined;
  /** Format as USD currency (default) or plain number. */
  @Input() mmCurrency = true;
  /** Fraction digits; defaults to 2 for currency, 0 for plain numbers. */
  @Input() mmDecimals: number | null = null;
  /** Force a leading + on positive values (for deltas). */
  @Input() mmSigned = false;
  /** Animation duration in seconds. */
  @Input() mmDur = 0.9;

  private current = 0;
  private playback: { stop: () => void } | null = null;
  private readonly reduced =
    typeof window !== 'undefined' &&
    !!window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  constructor(
    private el: ElementRef<HTMLElement>,
    private zone: NgZone
  ) {}

  ngOnChanges() {
    const target = Number(this.value ?? 0);
    if (!isFinite(target)) {
      return;
    }

    this.playback?.stop();

    if (this.reduced || target === this.current) {
      this.current = target;
      this.render(target);
      return;
    }

    const from = this.current;
    this.current = target;
    this.zone.runOutsideAngular(() => {
      this.playback = animate(from, target, {
        duration: this.mmDur,
        ease: [0.16, 1, 0.3, 1],
        onUpdate: (latest: number) => this.render(latest)
      });
    });
  }

  ngOnDestroy() {
    this.playback?.stop();
  }

  private render(value: number) {
    const decimals = this.mmDecimals ?? (this.mmCurrency ? 2 : 0);
    const formatted = this.mmCurrency
      ? new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals
        }).format(value)
      : new Intl.NumberFormat('en-US', {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals
        }).format(value);
    this.el.nativeElement.textContent = this.mmSigned && value > 0 ? `+${formatted}` : formatted;
  }
}
