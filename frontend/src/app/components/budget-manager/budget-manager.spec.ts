import { ComponentFixture, TestBed } from '@angular/core/testing';

import { BudgetManager } from './budget-manager';

describe('BudgetManager', () => {
  let component: BudgetManager;
  let fixture: ComponentFixture<BudgetManager>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BudgetManager]
    })
    .compileComponents();

    fixture = TestBed.createComponent(BudgetManager);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
