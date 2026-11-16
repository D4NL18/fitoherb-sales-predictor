import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Subject, of, throwError } from 'rxjs';
import { CatalogListResponse, CatalogProductItem } from '../../models/cross-sell.model';
import { AnalyticsService } from '../../services/analytics.service';
import { catalogResponse } from '../../testing/cross-sell-test-data';
import { ProductCatalogExplorerComponent } from './product-catalog-explorer.component';

function buildBulkCatalog(count: number): CatalogListResponse {
  const items: CatalogProductItem[] = Array.from({ length: count }, (_, idx) => ({
    codigo: 1000 + idx,
    descricao: `PRODUTO ${String(idx + 1).padStart(3, '0')}`,
    fornecedor: idx % 2 === 0 ? 'FORNECEDOR A' : 'FORNECEDOR B',
    estoque: idx % 3 === 0 ? 0 : idx + 1,
    precoVenda: 10 + idx,
  }));
  return catalogResponse(items);
}

describe('ProductCatalogExplorerComponent', () => {
  let fixture: ComponentFixture<ProductCatalogExplorerComponent>;
  let analyticsSpy: jasmine.SpyObj<AnalyticsService>;
  let element: HTMLElement;

  beforeEach(async () => {
    analyticsSpy = jasmine.createSpyObj<AnalyticsService>('AnalyticsService', ['getCatalogProducts']);
    analyticsSpy.getCatalogProducts.and.returnValue(of(catalogResponse()));

    await TestBed.configureTestingModule({
      imports: [ProductCatalogExplorerComponent],
      providers: [{ provide: AnalyticsService, useValue: analyticsSpy }],
    }).compileComponents();

    fixture = TestBed.createComponent(ProductCatalogExplorerComponent);
    element = fixture.nativeElement as HTMLElement;
  });

  it('exibe skeleton loader enquanto carrega e renderiza catálogo agrupado por fornecedor A→Z', () => {
    const pending$ = new Subject<CatalogListResponse>();
    analyticsSpy.getCatalogProducts.and.returnValue(pending$.asObservable());

    fixture.detectChanges();
    expect(element.querySelector('.explorer-skeleton[aria-busy="true"]')).not.toBeNull();

    pending$.next(catalogResponse());
    pending$.complete();
    fixture.detectChanges();

    expect(element.querySelector('.explorer-skeleton')).toBeNull();
    const groupHeaders = Array.from(element.querySelectorAll('.supplier-group-name')).map((el) =>
      (el.textContent ?? '').trim(),
    );
    expect(groupHeaders).toEqual(['APIS FLORA', 'CATARINENSE', 'INTEGRALMEDICA']);

    const rows = Array.from(element.querySelectorAll('tr.catalog-row .sku-cell')).map((el) =>
      (el.textContent ?? '').trim(),
    );
    // APIS FLORA (1042), CATARINENSE (1003 CAMOMILA, 1001 CHA VERDE), INTEGRALMEDICA (2002 WHEY)
    expect(rows).toEqual(['1042', '1003', '1001', '2002']);
  });

  it('exibe ErrorBanner em falha e refaz chamada ao clicar em Tentar novamente', () => {
    analyticsSpy.getCatalogProducts.and.returnValue(
      throwError(() => new Error('Network failure')),
    );
    fixture.detectChanges();

    const alert = element.querySelector('app-error-banner [role="alert"]');
    expect(alert).not.toBeNull();

    analyticsSpy.getCatalogProducts.and.returnValue(of(catalogResponse()));
    const retryBtn = element.querySelector('app-error-banner button') as HTMLButtonElement;
    retryBtn.click();
    fixture.detectChanges();

    expect(analyticsSpy.getCatalogProducts).toHaveBeenCalledTimes(2);
    expect(element.querySelectorAll('tr.catalog-row').length).toBe(4);
  });

  it('busca inteligente encontra "WHEY 100% PURE GELATO 900G" por "whey 100% gelato" e mostra empty state para "xyzw"', () => {
    fixture.detectChanges();

    const searchInput = element.querySelector('input[type="search"]') as HTMLInputElement;
    searchInput.value = 'whey 100% gelato';
    searchInput.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const rows = element.querySelectorAll('tr.catalog-row');
    expect(rows.length).toBe(1);
    expect(rows[0].textContent).toContain('WHEY 100% PURE GELATO 900G');

    searchInput.value = 'xyzw';
    searchInput.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    expect(element.querySelectorAll('tr.catalog-row').length).toBe(0);
    expect(element.textContent).toContain('Nenhum produto encontrado para os filtros aplicados');

    const clearBtn = element.querySelector('.catalog-empty-state button') as HTMLButtonElement;
    clearBtn.click();
    fixture.detectChanges();

    expect(element.querySelectorAll('tr.catalog-row').length).toBe(4);
  });

  it('não exibe botão redundante no cabeçalho de grupo e combina filtro por fornecedor com estoque', () => {
    fixture.detectChanges();

    expect(element.querySelector('.btn-filter-supplier')).toBeNull();

    const trigger = element.querySelector('.supplier-trigger') as HTMLButtonElement;
    trigger.click();
    fixture.detectChanges();

    const catOption = Array.from(element.querySelectorAll('.supplier-option')).find((opt) =>
      opt.textContent?.includes('CATARINENSE'),
    ) as HTMLElement;
    expect(catOption).toBeTruthy();
    catOption.click();
    fixture.detectChanges();

    expect(element.querySelectorAll('tr.catalog-row').length).toBe(2);

    const stockSelect = element.querySelector('select[id$="-stock"]') as HTMLSelectElement;
    stockSelect.value = 'out-of-stock';
    stockSelect.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    expect(element.querySelectorAll('tr.catalog-row').length).toBe(1);
    expect(element.querySelector('tr.catalog-row')?.textContent).toContain('CAMOMILA P/ CHÁ 30G');
  });

  it('exibe quantidade real de fornecedores (não de produtos) e busca dentro do select de Fornecedor', () => {
    fixture.detectChanges();

    const trigger = element.querySelector('.supplier-trigger') as HTMLButtonElement;
    expect(trigger).not.toBeNull();
    // 4 produtos pertencem a 3 fornecedores distintos (APIS FLORA, CATARINENSE, INTEGRALMEDICA)
    expect((trigger.textContent ?? '').replace(/\s+/g, ' ').trim()).toBe('Todos os fornecedores (3)');

    trigger.click();
    fixture.detectChanges();

    const supplierSearch = element.querySelector('.supplier-search-input') as HTMLInputElement;
    expect(supplierSearch).not.toBeNull();

    supplierSearch.value = 'integra';
    supplierSearch.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const options = Array.from(element.querySelectorAll('.supplier-option'));
    expect(options.length).toBe(1);
    expect(options[0].textContent).toContain('INTEGRALMEDICA');

    (options[0] as HTMLElement).click();
    fixture.detectChanges();

    expect(element.querySelectorAll('tr.catalog-row').length).toBe(1);
    expect(element.querySelector('tr.catalog-row')?.textContent).toContain('WHEY 100% PURE GELATO 900G');

    const clearSupBtn = element.querySelector('.btn-clear-supplier') as HTMLButtonElement;
    expect(clearSupBtn).not.toBeNull();
    clearSupBtn.click();
    fixture.detectChanges();

    expect(element.querySelectorAll('tr.catalog-row').length).toBe(4);
  });

  it('mantém agrupamento por fornecedor em qualquer ordenação e não exibe seletor de tamanho nem checkbox', () => {
    fixture.detectChanges();

    expect(element.querySelector('input[type="checkbox"]')).toBeNull();
    expect(element.querySelector('select[id$="-page-size"]')).toBeNull();

    const sortSelect = element.querySelector('select[id$="-sort"]') as HTMLSelectElement;
    sortSelect.value = 'price-desc';
    sortSelect.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    expect(element.querySelectorAll('.supplier-group-row').length).toBe(3);
    const skus = Array.from(element.querySelectorAll('tr.catalog-row .sku-cell')).map((el) =>
      (el.textContent ?? '').trim(),
    );
    expect(skus).toEqual(['2002', '1042', '1001', '1003']);
  });

  it('pagina sequencialmente com 50 itens por página exibindo fornecedores em sequência via ListPager', () => {
    analyticsSpy.getCatalogProducts.and.returnValue(of(buildBulkCatalog(65)));
    fixture.detectChanges();

    expect(element.querySelector('select[id$="-page-size"]')).toBeNull();
    expect(element.querySelectorAll('tr.catalog-row').length).toBe(50);

    const nextBtn = element.querySelector('app-list-pager button[aria-label="Próxima página"]') as HTMLButtonElement;
    nextBtn.click();
    fixture.detectChanges();

    expect(element.querySelectorAll('tr.catalog-row').length).toBe(15);
    expect(element.querySelectorAll('.supplier-group-row').length).toBeGreaterThan(0);
  });

  it('emite productSelect ao clicar na linha ou no botão de ação', () => {
    fixture.detectChanges();
    const emitted: CatalogProductItem[] = [];
    fixture.componentInstance.productSelect.subscribe((item) => emitted.push(item));

    const firstRow = element.querySelector('tr.catalog-row') as HTMLTableRowElement;
    firstRow.click();
    expect(emitted.length).toBe(1);
    expect(emitted[0].codigo).toBe(1042);

    const secondActionBtn = element.querySelectorAll('tr.catalog-row .btn-row-action')[1] as HTMLButtonElement;
    secondActionBtn.click();
    expect(emitted.length).toBe(2);
    expect(emitted[1].codigo).toBe(1003);
  });

  describe('modo showSeasonality = true', () => {
    const seasonalCatalog = catalogResponse([
      {
        codigo: 1042,
        descricao: 'EXTRATO DE PRÓPOLIS 30ML',
        fornecedor: 'APIS FLORA',
        estoque: 120,
        precoVenda: 28.5,
        forca: 'FORTE',
        amplitude: 0.77,
        mesPico: 'Mai–Jul',
        mesVale: 'Nov–Jan',
        faturamentoTotal: 145000,
        motivoInsuficiencia: null,
      },
      {
        codigo: 2002,
        descricao: 'WHEY 100% PURE GELATO 900G',
        fornecedor: 'INTEGRALMEDICA',
        estoque: 18,
        precoVenda: 159.9,
        forca: 'MODERADA',
        amplitude: 0.34,
        mesPico: 'Jan–Mar',
        mesVale: 'Jul–Set',
        faturamentoTotal: 320000,
        motivoInsuficiencia: null,
      },
      {
        codigo: 1003,
        descricao: 'CAMOMILA P/ CHÁ 30G',
        fornecedor: 'CATARINENSE',
        estoque: 0,
        precoVenda: 12.9,
        forca: 'INSUFICIENTE',
        amplitude: 0,
        mesPico: null,
        mesVale: null,
        faturamentoTotal: 1500,
        motivoInsuficiencia: 'VENDA_ESPORADICA',
      },
    ]);

    beforeEach(() => {
      analyticsSpy.getCatalogProducts.and.returnValue(of(seasonalCatalog));
      fixture.componentRef.setInput('showSeasonality', true);
      fixture.detectChanges();
    });

    it('solicita includeSeasonality=true e exibe colunas e filtro de força sazonal', () => {
      expect(analyticsSpy.getCatalogProducts).toHaveBeenCalledWith({ includeSeasonality: true });

      const text = element.textContent ?? '';
      expect(text).toContain('Força sazonal');
      expect(text).toContain('0,77x');
      expect(text).toContain('Mai–Jul');
      expect(text).toContain('Nov–Jan');
      expect(text).toContain('Venda esporádica (< 6 meses)');
      expect(element.querySelector('.supplier-group-row th')?.getAttribute('colspan')).toBe('11');
    });

    it('filtra por força sazonal e ordena por amplitude e faturamento', () => {
      const strengthSelect = element.querySelector('select[id$="-strength"]') as HTMLSelectElement;
      strengthSelect.value = 'measurable';
      strengthSelect.dispatchEvent(new Event('change'));
      fixture.detectChanges();

      expect(element.querySelectorAll('tr.catalog-row').length).toBe(2);

      const sortSelect = element.querySelector('select[id$="-sort"]') as HTMLSelectElement;
      sortSelect.value = 'revenue-desc';
      sortSelect.dispatchEvent(new Event('change'));
      fixture.detectChanges();

      let skus = Array.from(element.querySelectorAll('tr.catalog-row .sku-cell')).map((el) =>
        (el.textContent ?? '').trim(),
      );
      expect(skus).toEqual(['2002', '1042']);

      // Clique no cabeçalho Amplitude alterna amplitude-desc / amplitude-asc
      const ampHeaderBtn = Array.from(element.querySelectorAll('.sort-header-btn')).find((b) =>
        b.textContent?.includes('Amplitude'),
      ) as HTMLButtonElement;
      ampHeaderBtn.click();
      fixture.detectChanges();

      skus = Array.from(element.querySelectorAll('tr.catalog-row .sku-cell')).map((el) =>
        (el.textContent ?? '').trim(),
      );
      expect(skus).toEqual(['1042', '2002']);

      ampHeaderBtn.click();
      fixture.detectChanges();

      skus = Array.from(element.querySelectorAll('tr.catalog-row .sku-cell')).map((el) =>
        (el.textContent ?? '').trim(),
      );
      expect(skus).toEqual(['2002', '1042']);
    });
  });
});
