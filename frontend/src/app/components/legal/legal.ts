import { Component } from '@angular/core';
import { ViewportScroller } from '@angular/common';
import { RouterModule } from '@angular/router';
import {
  LucideArrowRight,
  LucideCircleCheck,
  LucideInfo,
  LucideMail,
  LucideShieldCheck
} from '@lucide/angular';
import { WordmarkComponent } from '../../shared/wordmark.component';

@Component({
  selector: 'app-legal',
  standalone: true,
  imports: [
    RouterModule,
    LucideArrowRight,
    LucideCircleCheck,
    LucideInfo,
    LucideMail,
    LucideShieldCheck,
    WordmarkComponent
  ],
  templateUrl: './legal.html',
  styleUrl: './legal.scss'
})
export class LegalComponent {
  constructor(viewportScroller: ViewportScroller) {
    // Anchor targets sit under the fixed topbar; scroll past it.
    viewportScroller.setOffset([0, 90]);
  }
}
