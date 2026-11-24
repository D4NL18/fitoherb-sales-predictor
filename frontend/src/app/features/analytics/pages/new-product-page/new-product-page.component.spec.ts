import { HttpErrorResponse } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { NewProductOptionsResponse } from '../../models/new-product.model';
import { AnalyticsService } from '../../services/analytics.service';
import { NewProductPageComponent } from './new-product-page.component';

const MOCK_OPTIONS: NewProductOptionsResponse = {
  data: {
    tipos: ['Tinturas'],
    fornecedores: ['FITOHERB LABORATORIOS'],
  },
  meta: { timestamp: '2026-11-17T10:00:00Z', version: '1.0.0', dataReferencia: '2026-11-16' },
};

describe('NewProductPageComponent', () => {
  let fixture: ComponentFixture<NewProductPageComponent>;
  let serviceSpy: jasmine.SpyObj<AnalyticsService>;

  beforeEach(async () => {
    serviceSpy = jasmine.createSpyObj<AnalyticsService>('AnalyticsService', [
      'getNewProductOptions',
      'simulateNewProductForecast',
    ]);
    serviceSpy.getNewProductOptions.and.returnValue(of(MOCK_OPTIONS));

    await TestBed.configureTestingModule({
      imports: [NewProductPageComponent],
      providers: [{ provide: AnalyticsService, useValue: serviceSpy }],
    }).compileComponents();

    fixture = TestBed.createComponent(NewProductPageComponent);
    fixture.detectChanges();
  });

  it('usa <h2> no título da seção e não cria <h1> duplicado', () => {
    const el: HTMLElement = fixture.nativeElement;
    expect(el.querySelector('h1')).toBeNull();
    expect(el.querySelector('h2.section-title')?.textContent).toContain(
      'Viabilidade de Produto Novo — Estimativa Conservadora',
    );
  });

  it('exibe estado NEW-001 em tone warning sem erro fatal quando base for insuficiente', () => {
    serviceSpy.simulateNewProductForecast.and.returnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 422,
            error: {
              error: {
                code: 'NEW-001',
                message: 'Base insuficiente para este tipo.',
                fields: [],
              },
            },
          }),
      ),
    );

    const select: HTMLSelectElement = fixture.nativeElement.querySelector('#np-tipo');
    select.value = 'Tinturas';
    select.dispatchEvent(new Event('change'));

    const supplierInput: HTMLInputElement = fixture.nativeElement.querySelector('#np-fornecedor');
    supplierInput.value = 'FITOHERB LABORATORIOS';
    supplierInput.dispatchEvent(new Event('input'));

    const descInput: HTMLInputElement = fixture.nativeElement.querySelector('#np-descricao');
    descInput.value = 'Tintura de Melissa 50ml';
    descInput.dispatchEvent(new Event('input'));

    const precoInput: HTMLInputElement = fixture.nativeElement.querySelector('#np-preco');
    precoInput.value = '42,50';
    precoInput.dispatchEvent(new Event('input'));

    fixture.detectChanges();
    fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit'));
    fixture.detectChanges();

    const stateEl: HTMLElement | null = fixture.nativeElement.querySelector('.result-state.tone-warning');
    expect(stateEl).not.toBeNull();
    expect(stateEl?.textContent).toContain('Base histórica insuficiente neste Tipo');
  });
});
