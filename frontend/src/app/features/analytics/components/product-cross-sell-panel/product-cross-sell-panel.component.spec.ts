/**
 * T-15 — Painel do modo produto (F-09, F-11; Design Plan §5.4–§5.9, §6).
 * Store e serviço mockados: o painel só desenha o estado e despacha ações.
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { ProductCrossSellPanelComponent } from './product-cross-sell-panel.component';
import { CrossSellStore } from '../../services/cross-sell.store';
import { AnalyticsService } from '../../services/analytics.service';
import { createFakeCrossSellStore, FakeCrossSellStore } from '../../testing/fake-cross-sell-store';
import {
  CONTRACT_MESSAGES,
  emptyProductResponse,
  productResponse,
  searchResponse,
} from '../../testing/cross-sell-test-data';
import { AnalyticsErrorCode } from '../../models/analytics.model';

describe('ProductCrossSellPanelComponent', () => {
  let fixture: ComponentFixture<ProductCrossSellPanelComponent>;
  let store: FakeCrossSellStore;
  let element: HTMLElement;

  beforeEach(async () => {
    store = createFakeCrossSellStore();
    const service = jasmine.createSpyObj<AnalyticsService>('AnalyticsService', ['searchProducts', 'getHealth']);
    service.searchProducts.and.returnValue(of(searchResponse()));
    await TestBed.configureTestingModule({
      imports: [ProductCrossSellPanelComponent],
      providers: [
        { provide: CrossSellStore, useValue: store },
        { provide: AnalyticsService, useValue: service },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(ProductCrossSellPanelComponent);
    element = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
  });

  function render(): string {
    fixture.detectChanges();
    return element.textContent ?? '';
  }

  function showError(code: AnalyticsErrorCode | null): void {
    store.product.status.set('error');
    store.product.error.set(code ? { code, message: CONTRACT_MESSAGES[code], fields: code === 'XSL-004' ? ['sku'] : [] } : null);
  }

  function submit(value: string): void {
    const input = element.querySelector('input') as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    (element.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    fixture.detectChanges();
  }

  it('estado inicial guia o usuário (intro), sem erro nem vazio', () => {
    const text = render();
    expect(text).toContain('Escolha um produto');
    expect(element.querySelector('[role="alert"]')).toBeNull();
  });

  it('envia o SKU validado ao store', () => {
    submit('1001');
    expect(store.searchProduct).toHaveBeenCalledOnceWith(1001);
  });

  it('valida o campo na tela: só dígitos, sem chamar o store', () => {
    submit('12a');
    expect(store.searchProduct).not.toHaveBeenCalled();
    expect(render()).toContain('Escolha um produto da lista ou digite o código (só números).');
    expect((element.querySelector('input') as HTMLInputElement).getAttribute('aria-invalid')).toBe('true');
  });

  it('carregando: skeleton com aria-busy e nenhum vazio', () => {
    store.product.status.set('loading');
    const text = render();

    expect(element.querySelector('[aria-busy="true"]')).not.toBeNull();
    expect(text).not.toContain('Nenhuma combinação forte');
    expect(text).toContain('Buscando');
  });

  it('sucesso: frases da explicação e sinalização semEstoque, sem margem nem números', () => {
    store.product.status.set('success');
    store.product.response.set(productResponse());
    const text = render();

    expect(text).toContain('CHA VERDE 100G');
    expect(text).toContain('Em 34% dos pedidos com CHA VERDE 100G também há CAPSULA DE HIBISCO.');
    expect(text).toContain('170 pedidos');
    expect(text).toContain('Sem estoque');
    expect(text).not.toContain('Margem');
    expect(text).not.toContain('Ver números');
    expect(element.querySelectorAll('ol li').length).toBe(2);
  });

  it('itens sinalizados mantêm a ordem da API (D-8)', () => {
    store.product.status.set('success');
    store.product.response.set(productResponse());
    render();

    const items = Array.from(element.querySelectorAll('ol li')).map((li) => li.textContent ?? '');
    expect(items[0]).toContain('CAPSULA DE HIBISCO');
    expect(items[1]).toContain('OLEO DE COCO 200ML');
    expect(items[0]).not.toContain('Sem estoque');
  });

  it('vazio do produto usa a descrição do produto consultado', () => {
    store.product.status.set('empty');
    store.product.response.set(emptyProductResponse());

    expect(render()).toContain('Nenhuma combinação forte para MEL DE ABELHA 500G');
  });

  it('XSL-001 aparece inline no campo', () => {
    showError('XSL-001');
    const text = render();

    expect(text).toContain(CONTRACT_MESSAGES['XSL-001']);
    expect((element.querySelector('input') as HTMLInputElement).getAttribute('aria-invalid')).toBe('true');
  });

  it('XSL-004 de sku vira a mensagem de validação', () => {
    showError('XSL-004');
    expect(render()).toContain('Digite só números, sem pontos ou letras.');
  });

  it('XSL-003 mostra o estado de dados insuficientes', () => {
    showError('XSL-003');
    expect(render()).toContain('Ainda não dá para recomendar com segurança');
  });

  it('falha técnica mostra banner role=alert com Tentar de novo e sem detalhes crus', () => {
    showError(null);
    render();

    const alert = element.querySelector('[role="alert"]');
    expect(alert?.textContent).toContain('Não foi possível buscar as sugestões agora');
    expect(alert?.textContent).toContain('Tentar de novo');
    expect(element.textContent).not.toContain('detail');
  });

  it('paginação: oculta com uma página, avança com Próxima', () => {
    store.product.status.set('success');
    store.product.response.set(productResponse());
    render();
    expect(findButton('Próxima')).toBeNull();

    store.product.response.set(productResponse({ totalItems: 120, totalPages: 3 }));
    render();
    findButton('Próxima')?.click();
    expect(store.goToPage).toHaveBeenCalledOnceWith(2);
  });

  function findButton(label: string): HTMLButtonElement | null {
    const buttons = Array.from(element.querySelectorAll('button')) as HTMLButtonElement[];
    return buttons.find((button) => (button.getAttribute('aria-label') ?? button.textContent ?? '').includes(label)) ?? null;
  }
});
