/**
 * Testes unitários para TrendSupplierGroupComponent (T-18, F-11).
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TrendSupplierGroupComponent } from './trend-supplier-group.component';
import { TrendParameters, TrendSupplierRow } from '../../models/sales-trend.model';
import { SupplierDetailState } from '../../services/sales-trend.store';

function createMockParameters(): TrendParameters {
  return {
    limiteBaseBaixaQuantidade: 10,
    limiteBaseBaixaFaturamento: 500,
    coberturaMinimaAnterior: 0.5,
    buscaMinCaracteres: 2,
    buscaMinCaracteresNumerica: 1,
    buscaMaxCaracteres: 60,
    ttlCacheHoras: 6,
  };
}

describe('TrendSupplierGroupComponent (F-11, T-18)', () => {
  let fixture: ComponentFixture<TrendSupplierGroupComponent>;
  let component: TrendSupplierGroupComponent;

  const mockSupplier: TrendSupplierRow = {
    fornecedor: 'LABORATÓRIO ALFA',
    fornecedorChave: 'f:laboratorio alfa',
    semFornecedor: false,
    qtdProdutos: 2,
    janelas: [
      {
        meses: 1,
        atual: 30,
        anterior: 70,
        variacaoPct: -57.1,
        status: 'VARIACAO',
        baseParcial: false,
        baseBaixa: false,
        devolucaoLiquida: false,
        atualPorDia: null,
        anteriorPorDia: null,
      },
      {
        meses: 3,
        atual: 120,
        anterior: 60,
        variacaoPct: 100.0,
        status: 'VARIACAO',
        baseParcial: false,
        baseBaixa: false,
        devolucaoLiquida: false,
        atualPorDia: null,
        anteriorPorDia: null,
      },
      {
        meses: 6,
        atual: 180,
        anterior: 120,
        variacaoPct: 50.0,
        status: 'VARIACAO',
        baseParcial: false,
        baseBaixa: false,
        devolucaoLiquida: false,
        atualPorDia: null,
        anteriorPorDia: null,
      },
      {
        meses: 12,
        atual: 300,
        anterior: 98,
        variacaoPct: 149.9,
        status: 'VARIACAO',
        baseParcial: true,
        baseBaixa: false,
        devolucaoLiquida: false,
        atualPorDia: 0.8219,
        anteriorPorDia: 0.3289,
      },
    ],
  };

  function createDetailState(): SupplierDetailState {
    return {
      supplierKey: 'f:laboratorio alfa',
      status: 'success',
      data: {
        data: [
          {
            codigo: 1001,
            descricao: 'CHÁ VERDE 100G',
            fornecedor: 'LABORATÓRIO ALFA',
            janelas: [
              {
                meses: 1,
                atual: 30,
                anterior: 20,
                variacaoPct: 50.0,
                status: 'VARIACAO',
                baseParcial: false,
                baseBaixa: false,
                devolucaoLiquida: false,
                atualPorDia: null,
                anteriorPorDia: null,
                contribuicaoPp: 14.3,
                contribuicaoValor: 10.0,
              },
            ],
          },
        ],
        meta: {
          timestamp: '2026-11-10T12:00:00Z',
          version: '1.0.0',
          dataReferencia: '2026-11-09',
          ultimoDiaCoberto: '2026-11-08',
          mesBase: '2026-10',
          mesBasePadrao: '2026-10',
          mesBaseMinimo: '2025-01',
          mesBaseMaximo: '2026-11',
          mesBaseParcial: false,
          metrica: 'revenue',
          janelas: [],
          parametros: createMockParameters(),
          page: 1,
          limit: 20,
          offset: 0,
          totalItems: 1,
          totalPages: 1,
          ordenacao: { por: 'contribution', janela: 3, sentido: 'desc' },
          fornecedor: mockSupplier,
        },
      },
      error: null,
      page: 1,
      limit: 20,
      offset: 0,
      sortBy: 'contribution',
      sortDir: 'desc',
      sortWindow: 3,
    };
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TrendSupplierGroupComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(TrendSupplierGroupComponent);
    component = fixture.componentInstance;
  });

  it('emite toggle ao clicar no botão de chevron de expansão', () => {
    fixture.componentRef.setInput('supplier', mockSupplier);
    fixture.componentRef.setInput('metric', 'revenue');
    fixture.componentRef.setInput('sortWindow', 3);
    fixture.componentRef.setInput('sortDir', 'desc');
    fixture.componentRef.setInput('isExpanded', false);
    fixture.detectChanges();

    spyOn(component.toggle, 'emit');
    const btn = fixture.nativeElement.querySelector('.expand-chevron-btn') as HTMLButtonElement;
    expect(btn.getAttribute('aria-expanded')).toBe('false');
    expect(btn.getAttribute('aria-controls')).toBeTruthy();
    btn.click();
    expect(component.toggle.emit).toHaveBeenCalled();
  });

  it('exibe valores do fornecedor, produtos filhos alinhados e emite sortChange', () => {
    fixture.componentRef.setInput('supplier', mockSupplier);
    fixture.componentRef.setInput('detailState', createDetailState());
    fixture.componentRef.setInput('metric', 'revenue');
    fixture.componentRef.setInput('sortWindow', 3);
    fixture.componentRef.setInput('sortDir', 'desc');
    fixture.componentRef.setInput('isExpanded', true);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.detail-header-row app-trend-row-values')).not.toBeNull();

    spyOn(component.sortChange, 'emit');
    const sortButtons = el.querySelectorAll('.sort-pill') as NodeListOf<HTMLButtonElement>;
    expect(sortButtons[0].getAttribute('aria-pressed')).toBe('true');
    expect(sortButtons[0].textContent).toContain('↓');

    sortButtons[1].click(); // Variação %
    expect(component.sortChange.emit).toHaveBeenCalledWith('variation');
  });

  it('expande valores detalhados ao clicar no chevron de um produto filho e recolhe no Escape', () => {
    fixture.componentRef.setInput('supplier', mockSupplier);
    fixture.componentRef.setInput('detailState', createDetailState());
    fixture.componentRef.setInput('metric', 'revenue');
    fixture.componentRef.setInput('sortWindow', 3);
    fixture.componentRef.setInput('sortDir', 'desc');
    fixture.componentRef.setInput('isExpanded', true);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const childBtn = el.querySelector('tr.detail-child-row .expand-chevron-btn') as HTMLButtonElement;
    expect(childBtn).not.toBeNull();
    expect(el.querySelector('.child-values-row')).toBeNull();

    childBtn.click();
    fixture.detectChanges();
    expect(el.querySelector('.child-values-row app-trend-row-values')).not.toBeNull();

    const childValuesRow = el.querySelector('.child-values-row') as HTMLElement;
    childValuesRow.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    fixture.detectChanges();
    expect(el.querySelector('.child-values-row')).toBeNull();

    spyOn(component.toggle, 'emit');
    const detailHeaderRow = el.querySelector('.detail-header-row') as HTMLElement;
    detailHeaderRow.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(component.toggle.emit).toHaveBeenCalled();
  });
});
