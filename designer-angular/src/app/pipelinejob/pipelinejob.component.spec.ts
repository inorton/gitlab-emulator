import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PipelinejobComponent } from './pipelinejob.component';

describe('PipelinejobComponent', () => {
  let component: PipelinejobComponent;
  let fixture: ComponentFixture<PipelinejobComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ PipelinejobComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(PipelinejobComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
