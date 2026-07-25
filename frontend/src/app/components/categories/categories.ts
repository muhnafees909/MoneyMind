import { Component, ElementRef, NgZone, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { animate, stagger } from 'motion';
import { LucideCheck, LucidePlus, LucideTrash2, LucideX } from '@lucide/angular';
import { CategoryService, CategoryInfo } from '../../services/category.service';
import { ModalService } from '../../services/modal.service';
import { CategoryIconComponent, PICKABLE_ICONS } from '../../shared/category-icon.component';

// Must match the backend's ALLOWED_COLORS (the design system category palette)
const PALETTE = [
  '#6c9de6', '#27b9de', '#dba43e', '#e27c4e',
  '#b189e0', '#a9bf49', '#e07b9f', '#8f93ea', '#86817a'
];

@Component({
  selector: 'app-categories',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    CategoryIconComponent,
    LucideCheck,
    LucidePlus,
    LucideTrash2,
    LucideX
  ],
  templateUrl: './categories.html',
  styleUrl: './categories.scss'
})
export class CategoriesComponent implements OnInit {
  categories: CategoryInfo[] = [];
  initialLoading = true;

  showAdd = false;
  saving = false;
  deletingId: number | null = null;

  readonly palette = PALETTE;
  readonly icons = PICKABLE_ICONS;
  readonly maxNameLen = 40;

  draft = { name: '', color: PALETTE[0], icon: 'tag' };

  preAnim = true;
  private entranceDone = false;
  private readonly reducedMotion =
    typeof window !== 'undefined' &&
    !!window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  constructor(
    private categoryService: CategoryService,
    private modalService: ModalService,
    private zone: NgZone,
    private host: ElementRef<HTMLElement>
  ) {
    if (this.reducedMotion) {
      this.preAnim = false;
    }
  }

  ngOnInit() {
    this.load();
  }

  private load() {
    this.categoryService.refresh().subscribe({
      next: () => {
        this.categories = this.categoryService.getAllCategories();
        this.finishLoad();
      },
      error: () => {
        this.categories = this.categoryService.getAllCategories();
        this.finishLoad();
      }
    });
  }

  private finishLoad() {
    this.initialLoading = false;
    setTimeout(() => this.runEntrance(), 40);
  }

  get systemCategories(): CategoryInfo[] {
    return this.categories.filter((c) => !c.isCustom);
  }

  get customCategories(): CategoryInfo[] {
    return this.categories.filter((c) => c.isCustom);
  }

  get nameError(): string | null {
    const name = this.draft.name.trim();
    if (!name) return null;
    if (name.length > this.maxNameLen) return `Keep it under ${this.maxNameLen} characters.`;
    const exists = this.categories.some(
      (c) => c.displayName.toLowerCase() === name.toLowerCase()
    );
    return exists ? 'A category with that name already exists.' : null;
  }

  get canCreate(): boolean {
    return !!this.draft.name.trim() && this.nameError === null && !this.saving;
  }

  toggleAdd() {
    this.showAdd = !this.showAdd;
    if (!this.showAdd) {
      this.resetDraft();
    }
  }

  private resetDraft() {
    this.draft = { name: '', color: this.palette[0], icon: 'tag' };
  }

  create() {
    if (!this.canCreate) {
      return;
    }
    this.saving = true;
    this.categoryService
      .createCategory(this.draft.name.trim(), this.draft.color, this.draft.icon)
      .subscribe({
        next: () => {
          this.saving = false;
          this.showAdd = false;
          this.resetDraft();
          this.categoryService.refresh().subscribe(() => {
            this.categories = this.categoryService.getAllCategories();
          });
        },
        error: (error) => {
          this.saving = false;
          this.modalService.showError(error?.error?.error || 'Could not create the category.');
        }
      });
  }

  async remove(cat: CategoryInfo) {
    if (cat.id == null) {
      return;
    }
    const confirmed = await this.modalService.showConfirm(
      `Delete “${cat.displayName}”? Any transactions using it will move to ` +
        `Uncategorized, and any budget for it will be removed. This can't be undone.`,
      'Delete category',
      'Delete',
      'Cancel'
    );
    if (!confirmed) {
      return;
    }
    this.deletingId = cat.id;
    this.categoryService.deleteCategory(cat.id).subscribe({
      next: () => {
        this.deletingId = null;
        this.categoryService.refresh().subscribe(() => {
          this.categories = this.categoryService.getAllCategories();
        });
      },
      error: (error) => {
        this.deletingId = null;
        this.modalService.showError(error?.error?.error || 'Could not delete the category.');
      }
    });
  }

  private runEntrance() {
    if (this.entranceDone) {
      return;
    }
    this.entranceDone = true;
    if (this.reducedMotion) {
      this.preAnim = false;
      return;
    }
    setTimeout(() => {
      const els = this.host.nativeElement.querySelectorAll('[data-animate]');
      this.preAnim = false;
      if (els.length === 0) {
        return;
      }
      this.zone.runOutsideAngular(() => {
        animate(
          els,
          { opacity: [0, 1], transform: ['translateY(10px)', 'translateY(0px)'] },
          { duration: 0.5, delay: stagger(0.05), ease: [0.22, 1, 0.36, 1] }
        );
      });
    });
  }
}
