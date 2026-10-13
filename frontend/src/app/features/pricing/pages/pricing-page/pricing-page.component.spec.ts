import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { PricingPageComponent } from './pricing-page.component';

describe('PricingPageComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PricingPageComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting()
      ]
    }).compileComponents();
  });

  it('should create the pricing page component', () => {
    const fixture = TestBed.createComponent(PricingPageComponent);
    const component = fixture.componentInstance;
    expect(component).toBeTruthy();
  });

  it('should render feature hero title and subtitle', () => {
    const fixture = TestBed.createComponent(PricingPageComponent);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.feature-title')?.textContent).toContain('Pricing Predictor');
    expect(compiled.querySelector('.feature-subtitle')?.textContent).toContain('Inteligência Comercial B2B');
  });

  it('should have all feature action buttons on main screen', () => {
    const fixture = TestBed.createComponent(PricingPageComponent);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.btn-help')).toBeTruthy();
    expect(compiled.querySelector('.btn-gear')).toBeTruthy();
    expect(compiled.querySelector('.btn-predict-main')).toBeTruthy();
    expect(compiled.querySelector('.btn-export-nav')).toBeTruthy();
  });
});
