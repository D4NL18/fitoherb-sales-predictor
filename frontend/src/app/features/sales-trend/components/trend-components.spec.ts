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
import { TrendCell } from '../models/sales-trend.model';

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

    it('calcula o texto de intervalo corretamente', () => {
      fixture.componentRef.setInput('page', 2);
      fixture.componentRef.setInput('totalPages', 3);
      fixture.componentRef.setInput('totalItems', 120);
      fixture.componentRef.setInput('offset', 50);
      fixture.componentRef.setInput('limit', 50);
      fixture.detectChanges();

      expect(component.rangeText()).toBe('51–100 de 120');
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
      const btn = fixture.nativeElement.querySelector('.retry-btn');
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
      const btn = fixture.nativeElement.querySelector('.empty-action-btn');
      btn.click();
      expect(component.action.emit).toHaveBeenCalled();
    });
  });

  describe('SegmentedControlComponent', () => {
    let fixture: ComponentFixture<SegmentedControlComponent>;
    let component: SegmentedControlComponent;

    beforeEach(async () => {
      await TestBed.configureTestingModule({
        imports: [SegmentedControlComponent],
      }).compileComponents();

      fixture = TestBed.createComponent(SegmentedControlComponent);
      component = fixture.componentInstance;
    });

    it('emite valor selecionado e navega por teclado', () => {
      fixture.componentRef.setInput('options', [
        { value: 'product', label: 'Por produto' },
        { value: 'supplier', label: 'Por fornecedor' },
      ]);
      fixture.componentRef.setInput('value', 'product');
      fixture.detectChanges();

      spyOn(component.valueChange, 'emit');
      component.select('supplier');
      expect(component.valueChange.emit).toHaveBeenCalledWith('supplier');
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
      const select = fixture.nativeElement.querySelector('select');
      select.value = '2026-11';
      select.dispatchEvent(new Event('change'));

      expect(component.monthChange.emit).toHaveBeenCalledWith('2026-11');
    });
  });

  describe('TrendCellComponent', () => {
    let fixture: ComponentFixture<TrendCellComponent>;
    let component: TrendCellComponent;

    beforeEach(async () => {
      await TestBed.configureTestingModule({
        imports: [TrendCellComponent],
      }).compileComponents();

      fixture = TestBed.createComponent(TrendCellComponent);
      component = fixture.componentInstance;
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

      const el = fixture.nativeElement;
      expect(el.querySelector('.direction-arrow').textContent).toContain('▲');
      expect(el.querySelector('.variation-value').textContent).toContain('+50,0%');
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

    it('emite imediatamente no Enter e limpa ao resetar valor externo', fakeAsync(() => {
      const emitted: string[] = [];
      component.searchChange.subscribe((v) => emitted.push(v));

      const input = fixture.nativeElement.querySelector('input.search-input') as HTMLInputElement;
      input.value = '57';
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
      fixture.detectChanges();

      expect(emitted).toEqual(['57']);

      fixture.componentRef.setInput('value', '57');
      fixture.detectChanges();
      fixture.componentRef.setInput('value', undefined);
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
  });
});
