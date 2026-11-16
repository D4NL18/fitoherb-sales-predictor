/**
 * T-15 — Painel do modo produto (F-09, F-11; Design Plan §5.4–§5.9, §6).
 * Store e serviço mockados: o painel só desenha o estado e despacha ações a partir do catálogo.
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { ProductCrossSellPanelComponent } from './product-cross-sell-panel.component';
import { CrossSellStore } from '../../services/cross-sell.store';
import { AnalyticsService } from '../../services/analytics.service';
import { createFakeCrossSellStore, FakeCrossSellStore } from '../../testing/fake-cross-sell-store';
import {
  CONTRACT_MESSAGES,
  catalogResponse,
  emptyProductResponse,
  productResponse,
} from '../../testing/cross-sell-test-data';
import { AnalyticsErrorCode } from '../../models/analytics.model';

describe('ProductCrossSellPanelComponent', () => {
  let fixture: ComponentFixture<ProductCrossSellPanelComponent>;
  let store: FakeCrossSellStore;
  let element: HTMLElement;

  beforeEach(async () => {
    store = createFakeCrossSellStore();
    const service = jasmine.createSpyObj<AnalyticsService>('AnalyticsService', [
      'getHealth',
      'getCatalogProducts',
    ]);
    service.getCatalogProducts.and.returnValue(of(catalogResponse()));
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
    store.product.error.set(
      code
        ? { code, message: CONTRACT_MESSAGES[code], fields: code === 'XSL-004' ? ['sku'] : [] }
        : null,
    );
  }

  it('estado inicial exibe apenas o catálogo unificado (sem app-code-search-form) e sem alertas', () => {
    const text = render();
    expect(element.querySelector('app-code-search-form')).toBeNull();
    expect(element.querySelector('app-product-catalog-explorer')).not.toBeNull();
    expect(text).toContain('Escolha um produto no catálogo');
    expect(element.querySelector('[role="alert"]')).toBeNull();
  });

  it('destaca linha no catálogo quando initialSku é informado', () => {
    fixture.componentRef.setInput('initialSku', '1001');
    fixture.detectChanges();

    const selectedRow = element.querySelector(
      'app-product-catalog-explorer tr.catalog-row.is-selected',
    );
    expect(selectedRow).not.toBeNull();
    expect(selectedRow?.textContent).toContain('CHA VERDE 100G');
  });

  it('filtra catálogo por "whey 100% gelato", seleciona produto e emite productSearched', () => {
    const searched: number[] = [];
    fixture.componentInstance.productSearched.subscribe((sku) => searched.push(sku));

    const searchInput = element.querySelector(
      'app-product-catalog-explorer input[type="search"]',
    ) as HTMLInputElement;
    expect(searchInput).not.toBeNull();

    searchInput.value = 'whey 100% gelato';
    searchInput.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const rows = element.querySelectorAll('app-product-catalog-explorer tr.catalog-row');
    expect(rows.length).toBe(1);
    expect(rows[0].textContent).toContain('WHEY 100% PURE GELATO 900G');

    const selectBtn = rows[0].querySelector('.btn-row-action') as HTMLButtonElement;
    expect(selectBtn.textContent?.trim()).toBe('Ver cross-sell');
    selectBtn.click();

    expect(store.searchProduct).toHaveBeenCalledOnceWith(2002);
    expect(searched).toEqual([2002]);
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

  it('vazio do produto usa a descrição do produto consultado e permite voltar ao catálogo', () => {
    store.product.status.set('empty');
    store.product.response.set(emptyProductResponse());

    expect(render()).toContain('Nenhuma combinação forte para MEL DE ABELHA 500G');
    const backBtn = findButton('Voltar para lista de produtos');
    expect(backBtn).not.toBeNull();
  });

  it('XSL-001 e XSL-004 exibem banner de alerta mantendo o catálogo visível', () => {
    showError('XSL-001');
    let text = render();
    expect(text).toContain(CONTRACT_MESSAGES['XSL-001']);
    expect(element.querySelector('[role="alert"]')).not.toBeNull();
    expect(element.querySelector('app-product-catalog-explorer')).not.toBeNull();

    showError('XSL-004');
    text = render();
    expect(text).toContain('Digite só números, sem pontos ou letras.');
  });

  it('XSL-003 mostra o estado de dados insuficientes', () => {
    showError('XSL-003');
    expect(render()).toContain('Ainda não dá para recomendar com segurança');
  });

  it('falha técnica mostra banner role=alert com Tentar de novo e botão voltar para lista', () => {
    showError(null);
    render();

    const alert = element.querySelector('[role="alert"]');
    expect(alert?.textContent).toContain('Não foi possível buscar as sugestões agora');
    expect(alert?.textContent).toContain('Tentar de novo');
    expect(element.textContent).not.toContain('detail');
    expect(findButton('Voltar para lista de produtos')).not.toBeNull();
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

  it('exibe botão "← Voltar para lista de produtos", chama clearSelection() e emite productCleared', () => {
    const cleared: boolean[] = [];
    fixture.componentInstance.productCleared.subscribe(() => cleared.push(true));

    store.product.status.set('success');
    store.product.response.set(productResponse());
    render();

    const backBtn = findButton('Voltar para lista de produtos');
    expect(backBtn).not.toBeNull();
    expect(backBtn!.textContent).toContain('←');
    backBtn!.click();
    render();

    expect(store.clearProduct).toHaveBeenCalledTimes(1);
    expect(cleared).toEqual([true]);
    expect(element.querySelector('app-product-catalog-explorer')).not.toBeNull();
  });

  function findButton(label: string): HTMLButtonElement | null {
    const buttons = Array.from(element.querySelectorAll('button')) as HTMLButtonElement[];
    return (
      buttons.find((button) =>
        (button.getAttribute('aria-label') ?? button.textContent ?? '').includes(label),
      ) ?? null
    );
  }
});
