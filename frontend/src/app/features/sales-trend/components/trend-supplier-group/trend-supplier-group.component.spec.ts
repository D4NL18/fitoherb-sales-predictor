/**
 * Testes unitários para TrendSupplierGroupComponent (T-18, F-11).
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TrendSupplierGroupComponent } from './trend-supplier-group.component';
import { TrendSupplierRow } from '../../models/sales-trend.model';
import { SupplierDetailState } from '../../services/sales-trend.store';

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
    const btn = fixture.nativeElement.querySelector('.expand-chevron-btn');
    btn.click();
    expect(component.toggle.emit).toHaveBeenCalled();
  });

  it('exibe produtos filhos e emite sortChange para ordenação dos filhos', () => {
    const detailState: SupplierDetailState = {
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
          parametros: {} as any,
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

    fixture.componentRef.setInput('supplier', mockSupplier);
    fixture.componentRef.setInput('detailState', detailState);
    fixture.componentRef.setInput('metric', 'revenue');
    fixture.componentRef.setInput('sortWindow', 3);
    fixture.componentRef.setInput('sortDir', 'desc');
    fixture.componentRef.setInput('isExpanded', true);
    fixture.detectChanges();

    spyOn(component.sortChange, 'emit');
    const sortButtons = fixture.nativeElement.querySelectorAll('.sort-pill');
    sortButtons[1].click(); // Variação %
    expect(component.sortChange.emit).toHaveBeenCalledWith('variation');
  });
});
