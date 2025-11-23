import { ComponentFixture, TestBed } from '@angular/core/testing';

import { GoalsManager } from './goals-manager';

describe('GoalsManager', () => {
  let component: GoalsManager;
  let fixture: ComponentFixture<GoalsManager>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GoalsManager]
    })
    .compileComponents();

    fixture = TestBed.createComponent(GoalsManager);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
