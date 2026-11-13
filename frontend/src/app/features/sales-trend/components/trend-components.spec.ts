/**
 * Testes unitários para componentes base e controles da Tendência de Vendas (T-18).
 */
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { TrendPagerComponent } from './trend-pager/trend-pager.component';
import { TrendErrorBannerComponent } from './trend-error-banner/trend-error-banner.component';
import { TrendEmptyStateComponent } from './trend-empty-state/trend-empty-state.component';
import { SegmentedControlComponent } from './segmented-control/segmented-control.component';
import { InlineNoticeComponent } from './inline-notice/inline-notice.component';
import { BaseMonthPickerComponent } from './base-month-picker/base-month-picker.component';
import { TrendSearchFieldComponent } from './trend-search-field/trend-search-field.component';
import { TrendToolbarComponent } from './trend-toolbar/trend-toolbar.component';
import { TrendCellComponent } from './trend-cell/trend-cell.component';
import { TrendRowValuesComponent } from './trend-row-values/trend-row-values.component';
import { ReadingGuideComponent } from './reading-guide/reading-guide.component';
import { TrendCardListComponent } from './trend-card-list/trend-card-list.component';
import {
  TrendCell,
  TrendDetailCell,
  TrendParameters,
  TrendSupplierRow,
} from '../models/sales-trend.model';
import { SupplierDetailState } from '../services/sales-trend.store';

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

describe('Sales Trend Components (T-18)', () => {
  describe('TrendPagerComponent', () => {
    let fixture: ComponentFixture<TrendPagerComponent>;
    let component: TrendPagerComponent;

    beforeEach(async () => {
      await TestBed.configureTestingModule({
        imports: [TrendPagerComponent],
      }).compileComponents();

      fixture = TestBed.createComponent(TrendPagerComponent);
      component = fixture.componentInstance;
    });

    it('emite pageChange ao clicar na próxima página', () => {
      fixture.componentRef.setInput('page', 1);
      fixture.componentRef.setInput('totalPages', 3);
      fixture.componentRef.setInput('totalItems', 120);
      fixture.componentRef.setInput('offset', 0);
      fixture.componentRef.setInput('limit', 50);
      fixture.detectChanges();

      spyOn(component.pageChange, 'emit');
      component.goTo(2);
      expect(component.pageChange.emit).toHaveBeenCalledWith(2);
    });

    it('calcula o texto de intervalo corretamente e não aplica aria-current em texto estático', () => {
      fixture.componentRef.setInput('page', 2);
      fixture.componentRef.setInput('totalPages', 3);
      fixture.componentRef.setInput('totalItems', 120);
      fixture.componentRef.setInput('offset', 50);
      fixture.componentRef.setInput('limit', 50);
      fixture.detectChanges();

      expect(component.rangeText()).toBe('51–100 de 120');
      const currentEl = fixture.nativeElement.querySelector('.pager-current') as HTMLElement;
      expect(currentEl.getAttribute('aria-current')).toBeNull();
    });
  });

  describe('TrendErrorBannerComponent', () => {
    let fixture: ComponentFixture<TrendErrorBannerComponent>;
    let component: TrendErrorBannerComponent;

    beforeEach(async () => {
      await TestBed.configureTestingModule({
        imports: [TrendErrorBannerComponent],
      }).compileComponents();

      fixture = TestBed.createComponent(TrendErrorBannerComponent);
      component = fixture.componentInstance;
    });

    it('emite evento retry ao clicar no botão de tentar novamente', () => {
      fixture.componentRef.setInput('message', 'Erro de conexão');
      fixture.detectChanges();

      spyOn(component.retry, 'emit');
      const btn = fixture.nativeElement.querySelector('.retry-btn') as HTMLButtonElement;
      btn.click();
      expect(component.retry.emit).toHaveBeenCalled();
    });
  });

  describe('TrendEmptyStateComponent', () => {
    let fixture: ComponentFixture<TrendEmptyStateComponent>;
    let component: TrendEmptyStateComponent;

    beforeEach(async () => {
      await TestBed.configureTestingModule({
        imports: [TrendEmptyStateComponent],
      }).compileComponents();

      fixture = TestBed.createComponent(TrendEmptyStateComponent);
      component = fixture.componentInstance;
    });

    it('exibe título, descrição e emite ação', () => {
      fixture.componentRef.setInput('title', 'Nenhum produto encontrado');
      fixture.componentRef.setInput('description', 'Tente ajustar os filtros');
      fixture.componentRef.setInput('actionLabel', 'Limpar filtros');
      fixture.detectChanges();

      spyOn(component.action, 'emit');
      const btn = fixture.nativeElement.querySelector('.empty-action-btn') as HTMLButtonElement;
      btn.click();
      expect(component.action.emit).toHaveBeenCalled();
    });
  });

  describe('SegmentedControlComponent', () => {
    let fixture: ComponentFixture<SegmentedControlComponent<unknown>>;
    let component: SegmentedControlComponent<unknown>;

    beforeEach(async () => {
      await TestBed.configureTestingModule({
        imports: [SegmentedControlComponent],
      }).compileComponents();

      fixture = TestBed.createComponent(SegmentedControlComponent);
      component = fixture.componentInstance;
    });

    it('emite valor selecionado e navega por teclado pulando itens desabilitados', () => {
      fixture.componentRef.setInput('label', 'Modo');
      fixture.componentRef.setInput('options', [
        { value: 'a', label: 'A' },
        { value: 'b', label: 'B', disabled: true },
        { value: 'c', label: 'C' },
      ]);
      fixture.componentRef.setInput('value', 'a');
      fixture.detectChanges();

      spyOn(component.valueChange, 'emit');
      const buttons = fixture.nativeElement.querySelectorAll('button.segment-item') as NodeListOf<HTMLButtonElement>;
      buttons[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));

      expect(component.valueChange.emit).toHaveBeenCalledWith('c');
    });
  });

  describe('BaseMonthPickerComponent', () => {
    let fixture: ComponentFixture<BaseMonthPickerComponent>;
    let component: BaseMonthPickerComponent;

    beforeEach(async () => {
      await TestBed.configureTestingModule({
        imports: [BaseMonthPickerComponent],
      }).compileComponents();

      fixture = TestBed.createComponent(BaseMonthPickerComponent);
      component = fixture.componentInstance;
    });

    it('gera apenas 2 opções: mês atual e mês passado', () => {
      fixture.componentRef.setInput('value', '2026-10');
      fixture.componentRef.setInput('defaultMonth', '2026-10');
      fixture.componentRef.setInput('maxMonth', '2026-11');
      fixture.componentRef.setInput('lastCoveredDay', '2026-11-08');
      fixture.detectChanges();

      const opts = component.monthOptions();
      expect(opts.length).toBe(2);
      expect(opts[0].value).toBe('2026-11');
      expect(opts[0].label).toContain('mês atual');
      expect(opts[1].value).toBe('2026-10');
      expect(opts[1].label).toContain('mês passado');
    });

    it('emite mês selecionado ao alterar o select', () => {
      fixture.componentRef.setInput('value', '2026-10');
      fixture.componentRef.setInput('defaultMonth', '2026-10');
      fixture.componentRef.setInput('maxMonth', '2026-11');
      fixture.detectChanges();

      spyOn(component.monthChange, 'emit');
      const select = fixture.nativeElement.querySelector('select') as HTMLSelectElement;
      select.value = '2026-11';
      select.dispatchEvent(new Event('change'));

      expect(component.monthChange.emit).toHaveBeenCalledWith('2026-11');
    });
  });

  describe('TrendCellComponent', () => {
    let fixture: ComponentFixture<TrendCellComponent>;

    beforeEach(async () => {
      await TestBed.configureTestingModule({
        imports: [TrendCellComponent],
      }).compileComponents();

      fixture = TestBed.createComponent(TrendCellComponent);
    });

    it('renderiza percentual com seta para cima quando variação é positiva', () => {
      const cell: TrendCell = {
        meses: 3,
        atual: 150,
        anterior: 100,
        variacaoPct: 50.0,
        status: 'VARIACAO',
        baseParcial: false,
        baseBaixa: false,
        devolucaoLiquida: false,
        atualPorDia: null,
        anteriorPorDia: null,
      };

      fixture.componentRef.setInput('cell', cell);
      fixture.componentRef.setInput('metric', 'revenue');
      fixture.detectChanges();

      const el = fixture.nativeElement as HTMLElement;
      expect(el.querySelector('.direction-arrow')?.textContent).toContain('▲');
      expect(el.querySelector('.variation-value')?.textContent).toContain('+50,0%');
    });

    it('exibe símbolo ▬ neutro para -0,04% arredondado para 0,0%', () => {
      const cell: TrendCell = {
        meses: 1,
        atual: 99.96,
        anterior: 100,
        variacaoPct: -0.04,
        status: 'VARIACAO',
        baseParcial: false,
        baseBaixa: false,
        devolucaoLiquida: false,
        atualPorDia: null,
        anteriorPorDia: null,
      };

      fixture.componentRef.setInput('cell', cell);
      fixture.componentRef.setInput('metric', 'revenue');
      fixture.detectChanges();

      const el = fixture.nativeElement as HTMLElement;
      expect(el.querySelector('.direction-arrow')?.textContent).toContain('▬');
      expect(el.querySelector('.variation-value')?.textContent).toContain('0,0%');
      expect(el.querySelector('.variation-row')?.classList.contains('is-down')).toBeFalse();
    });

    it('adiciona /dia no delta nominal de contribuição quando a base é parcial', () => {
      const detailCell: TrendDetailCell = {
        meses: 3,
        atual: 345.0,
        anterior: 314.8,
        variacaoPct: 816.6,
        status: 'VARIACAO',
        baseParcial: true,
        baseBaixa: false,
        devolucaoLiquida: false,
        atualPorDia: 31.3636,
        anteriorPorDia: 3.4217,
        contribuicaoPp: 20.5,
        contribuicaoValor: 27.94,
      };

      fixture.componentRef.setInput('cell', detailCell);
      fixture.componentRef.setInput('metric', 'revenue');
      fixture.detectChanges();

      const contribVal = fixture.nativeElement.querySelector('.contrib-val')?.textContent?.trim();
      expect(contribVal).toContain('R$');
      expect(contribVal).toContain('27,94/dia');
    });

    it('abre e fecha tooltip acessível por foco/teclado no selo de devolução', () => {
      const cell: TrendCell = {
        meses: 3,
        atual: 0,
        anterior: 100,
        variacaoPct: -100,
        status: 'VARIACAO',
        baseParcial: false,
        baseBaixa: false,
        devolucaoLiquida: true,
        atualPorDia: null,
        anteriorPorDia: null,
      };

      fixture.componentRef.setInput('cell', cell);
      fixture.componentRef.setInput('metric', 'revenue');
      fixture.detectChanges();

      const badgeBtn = fixture.nativeElement.querySelector('button.cell-badge') as HTMLButtonElement;
      expect(badgeBtn).not.toBeNull();

      badgeBtn.dispatchEvent(new FocusEvent('focus'));
      fixture.detectChanges();
      expect(fixture.nativeElement.querySelector('[role="tooltip"]')?.textContent).toContain('devoluções');

      badgeBtn.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      fixture.detectChanges();
      expect(fixture.nativeElement.querySelector('[role="tooltip"]')).toBeNull();
    });
  });

  describe('TrendSearchFieldComponent', () => {
    let fixture: ComponentFixture<TrendSearchFieldComponent>;
    let component: TrendSearchFieldComponent;

    beforeEach(async () => {
      await TestBed.configureTestingModule({
        imports: [TrendSearchFieldComponent],
      }).compileComponents();

      fixture = TestBed.createComponent(TrendSearchFieldComponent);
      component = fixture.componentInstance;
      fixture.detectChanges();
    });

    it('mantém digitação contínua com debounce sem perder rascunho nem espaço final', fakeAsync(() => {
      const emitted: string[] = [];
      component.searchChange.subscribe((v) => emitted.push(v));

      const input = fixture.nativeElement.querySelector('input.search-input') as HTMLInputElement;

      input.value = 'c';
      input.dispatchEvent(new Event('input'));
      fixture.detectChanges();
      tick(250);
      expect(emitted).toEqual([]);
      expect(input.value).toBe('c');

      input.value = 'cha ';
      input.dispatchEvent(new Event('input'));
      fixture.detectChanges();
      tick(250);
      expect(emitted).toEqual(['cha ']);

      // Simula retorno do parent com valor trimado (?q=cha): não deve apagar o espaço em digitação
      fixture.componentRef.setInput('value', 'cha');
      fixture.detectChanges();
      expect(input.value).toBe('cha ');
    }));

    it('emite imediatamente no Enter, limpa no Escape e ao clicar no botão limpar', fakeAsync(() => {
      const emitted: string[] = [];
      component.searchChange.subscribe((v) => emitted.push(v));

      const input = fixture.nativeElement.querySelector('input.search-input') as HTMLInputElement;
      input.value = '57';
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
      fixture.detectChanges();

      expect(emitted).toEqual(['57']);

      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      fixture.detectChanges();
      expect(input.value).toBe('');
      expect(emitted).toEqual(['57', '']);

      fixture.componentRef.setInput('value', '57');
      fixture.detectChanges();
      const clearBtn = fixture.nativeElement.querySelector('.clear-btn') as HTMLButtonElement;
      expect(clearBtn).not.toBeNull();
      clearBtn.click();
      fixture.detectChanges();
      expect(input.value).toBe('');
      tick(300);
    }));
  });

  describe('TrendToolbarComponent', () => {
    let fixture: ComponentFixture<TrendToolbarComponent>;

    beforeEach(async () => {
      await TestBed.configureTestingModule({
        imports: [TrendToolbarComponent],
      }).compileComponents();

      fixture = TestBed.createComponent(TrendToolbarComponent);
    });

    it('nunca desabilita o campo de busca enquanto loading é true', () => {
      fixture.componentRef.setInput('query', { groupBy: 'product', metric: 'revenue' });
      fixture.componentRef.setInput('loading', true);
      fixture.detectChanges();

      const searchInput = fixture.nativeElement.querySelector('input.search-input') as HTMLInputElement;
      expect(searchInput).toBeTruthy();
      expect(searchInput.disabled).toBeFalse();
    });

    it('alterna texto e placeholder do filtro mínimo conforme métrica selecionada', () => {
      fixture.componentRef.setInput('query', { groupBy: 'product', metric: 'revenue' });
      fixture.detectChanges();

      const label = fixture.nativeElement.querySelector('.volume-label') as HTMLLabelElement;
      const input = fixture.nativeElement.querySelector('#min-volume-input') as HTMLInputElement;
      const unit = fixture.nativeElement.querySelector('.volume-unit') as HTMLElement;

      expect(label.textContent?.trim()).toBe('Faturamento mínimo:');
      expect(input.placeholder).toBe('0,00');
      expect(unit.textContent?.trim()).toBe('R$');

      fixture.componentRef.setInput('query', { groupBy: 'product', metric: 'quantity' });
      fixture.detectChanges();

      expect(label.textContent?.trim()).toBe('Volume mínimo:');
      expect(input.placeholder).toBe('0');
      expect(unit.textContent?.trim()).toBe('un');
    });

    it('valida valor negativo no filtro mínimo exibindo erro inline e zerando corte', () => {
      fixture.componentRef.setInput('query', { groupBy: 'product', metric: 'revenue' });
      fixture.detectChanges();

      const emitted: number[] = [];
      fixture.componentInstance.minVolumeChange.subscribe((v) => emitted.push(v));

      const input = fixture.nativeElement.querySelector('#min-volume-input') as HTMLInputElement;
      input.value = '-25';
      input.dispatchEvent(new Event('change'));
      fixture.detectChanges();

      expect(emitted).toEqual([0]);
      expect(fixture.nativeElement.querySelector('#min-volume-error')?.textContent).toContain('maior que zero');
    });
  });

  describe('TrendRowValuesComponent', () => {
    let fixture: ComponentFixture<TrendRowValuesComponent>;

    beforeEach(async () => {
      await TestBed.configureTestingModule({
        imports: [TrendRowValuesComponent],
      }).compileComponents();

      fixture = TestBed.createComponent(TrendRowValuesComponent);
    });

    it('preserva casas decimais em quantidades fracionárias no modo average', () => {
      const janelas: TrendCell[] = [
        {
          meses: 3,
          atual: 1,
          anterior: 0.333,
          variacaoPct: 200.0,
          status: 'VARIACAO',
          baseParcial: false,
          baseBaixa: true,
          devolucaoLiquida: false,
          atualPorDia: null,
          anteriorPorDia: null,
        },
      ];

      fixture.componentRef.setInput('janelas', janelas);
      fixture.componentRef.setInput('metric', 'quantity');
      fixture.detectChanges();

      const cells = Array.from(
        fixture.nativeElement.querySelectorAll('td.cell-val') as NodeListOf<HTMLElement>
      ).map((el) => el.textContent?.trim());
      expect(cells).toEqual(['1 un', '0,3 un']);
    });
  });

  describe('ReadingGuideComponent', () => {
    let fixture: ComponentFixture<ReadingGuideComponent>;

    beforeEach(async () => {
      await TestBed.configureTestingModule({
        imports: [ReadingGuideComponent],
      }).compileComponents();

      fixture = TestBed.createComponent(ReadingGuideComponent);
      fixture.detectChanges();
    });

    it('fecha o guia expansível ao pressionar Escape', () => {
      const details = fixture.nativeElement.querySelector('details.reading-guide-details') as HTMLDetailsElement;
      details.open = true;
      fixture.detectChanges();

      details.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      fixture.detectChanges();
      expect(details.open).toBeFalse();
    });
  });

  describe('TrendCardListComponent', () => {
    let fixture: ComponentFixture<TrendCardListComponent>;

    beforeEach(async () => {
      await TestBed.configureTestingModule({
        imports: [TrendCardListComponent],
      }).compileComponents();

      fixture = TestBed.createComponent(TrendCardListComponent);
    });

    it('renderiza drill-down de fornecedor no mobile e emite detailSortChange', () => {
      const supplier: TrendSupplierRow = {
        fornecedor: 'LAB MOBILE',
        fornecedorChave: 'f:lab mobile',
        semFornecedor: false,
        qtdProdutos: 1,
        janelas: [
          {
            meses: 3,
            atual: 300,
            anterior: 200,
            variacaoPct: 50,
            status: 'VARIACAO',
            baseParcial: false,
            baseBaixa: false,
            devolucaoLiquida: false,
            atualPorDia: null,
            anteriorPorDia: null,
          },
        ],
      };

      const detailMap = new Map<string, SupplierDetailState>([
        [
          'f:lab mobile',
          {
            supplierKey: 'f:lab mobile',
            status: 'success',
            data: {
              data: [
                {
                  codigo: 500,
                  descricao: 'CHÁ MOBILE',
                  fornecedor: 'LAB MOBILE',
                  janelas: [
                    {
                      meses: 3,
                      atual: 300,
                      anterior: 200,
                      variacaoPct: 50,
                      status: 'VARIACAO',
                      baseParcial: false,
                      baseBaixa: false,
                      devolucaoLiquida: false,
                      atualPorDia: null,
                      anteriorPorDia: null,
                      contribuicaoPp: 50,
                      contribuicaoValor: 100,
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
                fornecedor: supplier,
              },
            },
            error: null,
            page: 1,
            limit: 20,
            offset: 0,
            sortBy: 'contribution',
            sortDir: 'desc',
            sortWindow: 3,
          },
        ],
      ]);

      fixture.componentRef.setInput('items', [supplier]);
      fixture.componentRef.setInput('groupBy', 'supplier');
      fixture.componentRef.setInput('metric', 'revenue');
      fixture.componentRef.setInput('sortWindow', 3);
      fixture.componentRef.setInput('sortDir', 'desc');
      fixture.componentRef.setInput('expandedKeys', new Set(['f:lab mobile']));
      fixture.componentRef.setInput('details', detailMap);
      fixture.detectChanges();

      const el = fixture.nativeElement as HTMLElement;
      expect(el.querySelector('.mobile-child-title')?.textContent).toContain('CHÁ MOBILE');

      spyOn(fixture.componentInstance.detailSortChange, 'emit');
      const pills = el.querySelectorAll('.sort-pill') as NodeListOf<HTMLButtonElement>;
      pills[1].click();
      expect(fixture.componentInstance.detailSortChange.emit).toHaveBeenCalledWith({
        supplierKey: 'f:lab mobile',
        sortBy: 'variation',
      });
    });
  });

  describe('InlineNoticeComponent', () => {
    it('renderiza aviso dismissible e emite evento ao fechar', async () => {
      await TestBed.configureTestingModule({
        imports: [InlineNoticeComponent],
      }).compileComponents();

      const fixture = TestBed.createComponent(InlineNoticeComponent);
      fixture.componentRef.setInput('text', 'Filtros redefinidos.');
      fixture.componentRef.setInput('dismissible', true);
      fixture.detectChanges();

      spyOn(fixture.componentInstance.dismiss, 'emit');
      const dismissBtn = fixture.nativeElement.querySelector('.notice-dismiss-btn') as HTMLButtonElement;
      dismissBtn.click();
      expect(fixture.componentInstance.dismiss.emit).toHaveBeenCalled();
    });
  });
});
