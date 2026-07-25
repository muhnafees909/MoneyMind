import { Component, Input } from '@angular/core';
import {
  LucideArrowDownLeft,
  LucideArrowUpRight,
  LucideBaby,
  LucideBanknote,
  LucideBook,
  LucideBriefcase,
  LucideBuilding2,
  LucideCar,
  LucideCircleDashed,
  LucideClapperboard,
  LucideCoffee,
  LucideCreditCard,
  LucideDog,
  LucideDumbbell,
  LucideGamepad2,
  LucideGift,
  LucideGraduationCap,
  LucideHammer,
  LucideHeartPulse,
  LucideHouse,
  LucideLandmark,
  LucideMusic,
  LucidePhone,
  LucidePiggyBank,
  LucidePlane,
  LucidePlug,
  LucideReceipt,
  LucideShirt,
  LucideShoppingBag,
  LucideShoppingCart,
  LucideSparkles,
  LucideTag,
  LucideUtensils,
  LucideWifi,
  LucideWrench
} from '@lucide/angular';

/**
 * The curated set of lucide icons a category can use (kebab-case names,
 * matching the backend's ALLOWED_ICONS). `PICKABLE_ICONS` drives the create
 * form's icon grid; the switch below renders any of them (plus default-only
 * icons) by name.
 */
export const PICKABLE_ICONS: string[] = [
  'tag', 'utensils', 'coffee', 'shopping-bag', 'shopping-cart', 'car',
  'house', 'plane', 'heart-pulse', 'dumbbell', 'gift', 'graduation-cap',
  'baby', 'dog', 'gamepad-2', 'music', 'shirt', 'wrench', 'plug', 'wifi',
  'phone', 'book', 'briefcase', 'piggy-bank', 'credit-card', 'banknote',
  'sparkles', 'clapperboard', 'hammer', 'building-2', 'landmark', 'receipt'
];

/** Renders a category's lucide icon by its kebab-case name. */
@Component({
  selector: 'app-category-icon',
  standalone: true,
  imports: [
    LucideArrowDownLeft, LucideArrowUpRight, LucideBaby, LucideBanknote,
    LucideBook, LucideBriefcase, LucideBuilding2, LucideCar, LucideCircleDashed,
    LucideClapperboard, LucideCoffee, LucideCreditCard, LucideDog, LucideDumbbell,
    LucideGamepad2, LucideGift, LucideGraduationCap, LucideHammer, LucideHeartPulse,
    LucideHouse, LucideLandmark, LucideMusic, LucidePhone, LucidePiggyBank,
    LucidePlane, LucidePlug, LucideReceipt, LucideShirt, LucideShoppingBag,
    LucideShoppingCart, LucideSparkles, LucideTag, LucideUtensils, LucideWifi,
    LucideWrench
  ],
  template: `
    @switch (name) {
      @case ('utensils') { <svg lucideUtensils [size]="size"></svg> }
      @case ('coffee') { <svg lucideCoffee [size]="size"></svg> }
      @case ('shopping-bag') { <svg lucideShoppingBag [size]="size"></svg> }
      @case ('shopping-cart') { <svg lucideShoppingCart [size]="size"></svg> }
      @case ('car') { <svg lucideCar [size]="size"></svg> }
      @case ('house') { <svg lucideHouse [size]="size"></svg> }
      @case ('plane') { <svg lucidePlane [size]="size"></svg> }
      @case ('heart-pulse') { <svg lucideHeartPulse [size]="size"></svg> }
      @case ('dumbbell') { <svg lucideDumbbell [size]="size"></svg> }
      @case ('gift') { <svg lucideGift [size]="size"></svg> }
      @case ('graduation-cap') { <svg lucideGraduationCap [size]="size"></svg> }
      @case ('baby') { <svg lucideBaby [size]="size"></svg> }
      @case ('dog') { <svg lucideDog [size]="size"></svg> }
      @case ('gamepad-2') { <svg lucideGamepad2 [size]="size"></svg> }
      @case ('music') { <svg lucideMusic [size]="size"></svg> }
      @case ('shirt') { <svg lucideShirt [size]="size"></svg> }
      @case ('wrench') { <svg lucideWrench [size]="size"></svg> }
      @case ('plug') { <svg lucidePlug [size]="size"></svg> }
      @case ('wifi') { <svg lucideWifi [size]="size"></svg> }
      @case ('phone') { <svg lucidePhone [size]="size"></svg> }
      @case ('book') { <svg lucideBook [size]="size"></svg> }
      @case ('briefcase') { <svg lucideBriefcase [size]="size"></svg> }
      @case ('piggy-bank') { <svg lucidePiggyBank [size]="size"></svg> }
      @case ('credit-card') { <svg lucideCreditCard [size]="size"></svg> }
      @case ('banknote') { <svg lucideBanknote [size]="size"></svg> }
      @case ('sparkles') { <svg lucideSparkles [size]="size"></svg> }
      @case ('clapperboard') { <svg lucideClapperboard [size]="size"></svg> }
      @case ('hammer') { <svg lucideHammer [size]="size"></svg> }
      @case ('building-2') { <svg lucideBuilding2 [size]="size"></svg> }
      @case ('landmark') { <svg lucideLandmark [size]="size"></svg> }
      @case ('receipt') { <svg lucideReceipt [size]="size"></svg> }
      @case ('arrow-down-left') { <svg lucideArrowDownLeft [size]="size"></svg> }
      @case ('arrow-up-right') { <svg lucideArrowUpRight [size]="size"></svg> }
      @case ('circle-dashed') { <svg lucideCircleDashed [size]="size"></svg> }
      @default { <svg lucideTag [size]="size"></svg> }
    }
  `
})
export class CategoryIconComponent {
  @Input() name: string | null | undefined = 'tag';
  @Input() size = 16;
}
