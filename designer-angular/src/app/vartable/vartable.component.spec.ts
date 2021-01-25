import { ComponentFixture, TestBed } from '@angular/core/testing';

import { VartableComponent } from './vartable.component';

describe('VartableComponent', () => {
  let component: VartableComponent;
  let fixture: ComponentFixture<VartableComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ VartableComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(VartableComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
