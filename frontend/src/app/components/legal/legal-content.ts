import { Component, ElementRef } from '@angular/core';
import { LucideCircleCheck, LucideInfo, LucideMail } from '@lucide/angular';

/**
 * The Terms of Service + Privacy Policy document body — the single source of
 * truth for this text. Rendered both by the standalone /legal page and the
 * Terms/Privacy modal, so the content lives in exactly one place.
 *
 * Internal cross-references ("see the Privacy Policy below") scroll within
 * whatever scroll container hosts this component (the window on the page, the
 * modal body in the dialog) via scrollIntoView — no router navigation, so it
 * works identically in both contexts.
 */
@Component({
  selector: 'app-legal-content',
  standalone: true,
  imports: [LucideCircleCheck, LucideInfo, LucideMail],
  templateUrl: './legal-content.html',
  styleUrl: './legal-content.scss'
})
export class LegalContentComponent {
  constructor(private host: ElementRef<HTMLElement>) {}

  /** Scroll a section (e.g. 'terms', 'privacy') into view within the host's
   *  nearest scroll container. Used by internal cross-links and the modal nav. */
  scrollTo(id: string, event?: Event, behavior: ScrollBehavior = 'smooth'): void {
    event?.preventDefault();
    const el = this.host.nativeElement.querySelector('#' + id) as HTMLElement | null;
    el?.scrollIntoView({ behavior, block: 'start' });
  }
}
