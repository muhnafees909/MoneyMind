import { AfterViewInit, Component, Inject, ViewChild } from '@angular/core';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { LucideX } from '@lucide/angular';
import { LegalContentComponent } from '../../legal/legal-content';

export interface LegalModalData {
  /** Which document to scroll to on open. Defaults to 'terms'. */
  section?: 'terms' | 'privacy';
}

/**
 * Terms of Service / Privacy Policy shown as a modal over the current screen.
 * Chrome (backdrop, elevation, entrance/exit) comes from Material's dialog +
 * the global overrides in styles.scss; the long document body scrolls
 * internally within a fixed-height panel (never the page behind it).
 */
@Component({
  selector: 'app-legal-modal',
  standalone: true,
  imports: [MatDialogModule, LucideX, LegalContentComponent],
  templateUrl: './legal-modal.html',
  styleUrl: './legal-modal.scss'
})
export class LegalModalComponent implements AfterViewInit {
  @ViewChild(LegalContentComponent) content!: LegalContentComponent;

  active: 'terms' | 'privacy';

  constructor(
    public dialogRef: MatDialogRef<LegalModalComponent>,
    @Inject(MAT_DIALOG_DATA) public data: LegalModalData
  ) {
    this.active = data?.section === 'privacy' ? 'privacy' : 'terms';
  }

  ngAfterViewInit(): void {
    // Jump straight to the requested document (instant — no scroll animation on open).
    if (this.data?.section === 'privacy') {
      setTimeout(() => this.content.scrollTo('privacy', undefined, 'auto'));
    }
  }

  goto(section: 'terms' | 'privacy'): void {
    this.active = section;
    this.content.scrollTo(section);
  }

  close(): void {
    this.dialogRef.close();
  }
}
