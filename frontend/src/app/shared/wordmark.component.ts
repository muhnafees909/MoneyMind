import { Component, Input } from '@angular/core';

/**
 * The MoneyMind wordmark with the Currency Glyph identity: the leading M
 * carries a double strikethrough (like $, ¥, ₩, ₦), set in fern, with the
 * rest of the name in primary ink. The name itself is the logo — the
 * standalone struck-M glyph (public/mm-mark.svg, favicon.svg) is used only
 * where the name doesn't appear.
 *
 * Bars are em-sized, so the treatment scales with the `size` input.
 */
@Component({
  selector: 'mm-wordmark',
  standalone: true,
  template: `
    <span class="cg" [style.font-size.px]="size"
      ><span class="m">M<i class="bar b1"></i><i class="bar b2"></i></span
      ><span class="rest">oneyMind</span></span
    >
  `,
  styles: [
    `
      .cg {
        font-family: var(--mm-font-serif);
        font-weight: 600;
        letter-spacing: -0.01em;
        line-height: 1;
        display: inline-block;
        white-space: nowrap;
      }

      .m {
        position: relative;
        display: inline-block;
        color: var(--mm-brand);
        margin-right: 0.015em;
      }

      .rest {
        color: var(--mm-text-1);
        transition: color var(--mm-dur-fast) ease;
      }

      /* Hover state when the wordmark is wrapped in a link (nav, footer):
         the name warms toward fern, matching link hovers elsewhere */
      :host-context(a:hover) .rest {
        color: var(--mm-brand-strong);
      }

      .bar {
        position: absolute;
        left: -0.06em;
        right: -0.05em;
        height: 0.075em;
        border-radius: 0.04em;
        background: var(--mm-brand);
        display: block;
      }

      .b1 {
        top: 0.375em;
      }

      .b2 {
        top: 0.53em;
      }
    `
  ]
})
export class WordmarkComponent {
  @Input() size = 17;
}
