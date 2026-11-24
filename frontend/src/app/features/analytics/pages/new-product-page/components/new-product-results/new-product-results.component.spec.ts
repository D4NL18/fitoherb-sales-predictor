import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NewProductForecastData } from '../../../../models/new-product.model';
import { NewProductResultsComponent } from './new-product-results.component';

const MOCK_DATA: NewProductForecastData = {
  inputSummary: {
    tipo: 'Tinturas',
    fornecedor: 'FITOHERB LABORATORIOS',
    descricao: 'Tintura de Melissa 50ml',
    precoVendaPrevisto: 42.5,
    custoUnitario: 19.1,
    margemMinimaDesejada: 0.5,
    horizonMonths: 3,
  },
  monthlyForecast: [
    {
      month: 1,
      calendarMonth: 11,
      quantity: 38,
      revenue: 1615,
      grossMargin: 889.2,
      p10Quantity: 22,
      conservativeQuantity: 38,
      p50Quantity: 64,
      similarP25Quantity: 54,
      seasonalityFactor: 1,
      seasonalityConfidence: 'BAIXA',
    },
    {
      month: 2,
      calendarMonth: 12,
      quantity: 44,
      revenue: 1870,
      grossMargin: 1029.6,
      p10Quantity: 26,
      conservativeQuantity: 44,
      p50Quantity: 72,
      similarP25Quantity: 63,
      seasonalityFactor: 1,
      seasonalityConfidence: 'BAIXA',
    },
  ],
  seasonalityStatus: 'FALLBACK_NEUTRAL',
  aggregatedTotals: {
    totalQuantity: 82,
    totalRevenue: 3485,
    totalGrossMargin: 1918.8,
    averageMonthlyQuantity: 41,
    averageMonthlyRevenue: 1742.5,
  },
  financialViability: {
    precoVenda: 42.5,
    custoUnitario: 19.1,
    margemBrutaUnitaria: 23.4,
    margemBrutaPercentual: 0.5506,
    margemMinimaDesejada: 0.5,
    viavel: true,
    parecer: 'Produto viável.',
  },
  marketCeiling: {
    tetoMaduroP75: 210,
    descricao: 'Percentil 75 de produtos maduros.',
  },
  similarsUsed: [
    {
      sku: '1042',
      descricao: 'Tintura de Passiflora 50ml',
      fornecedor: 'FITOHERB LABORATORIOS',
      primeiraVenda: '2025-05-10',
      precoHistorico: 39.9,
      scoreFinal: 0.9125,
      scoreFornecedor: 1,
      scorePreco: 0.9388,
      scoreTfidf: 0.835,
      quantidadesPrimeirosMeses: [58, 65, 80],
    },
  ],
  methodologyNotice: 'Estimativa conservadora P25 x 0,70.',
};

describe('NewProductResultsComponent', () => {
  let fixture: ComponentFixture<NewProductResultsComponent>;
  let component: NewProductResultsComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NewProductResultsComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(NewProductResultsComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('data', MOCK_DATA);
    fixture.detectChanges();
  });

  it('renderiza selo conservador, tag positiva e callout neutro de sazonalidade F1', () => {
    const el: HTMLElement = fixture.nativeElement;
    expect(el.querySelector('.seal-title')?.textContent).toContain(
      'Estimativa Conservadora: calculada para proteger seu estoque',
    );
    expect(el.querySelector('.tag.tag-positive')?.textContent).toContain('Viável para Lançamento');
    expect(el.querySelector('.seasonality-callout')?.textContent).toContain('fator neutro (1,00×)');
  });

  it('renderiza gráfico SVG acessível (role=img) + tabela ledger e bloco segregado P75', () => {
    const el: HTMLElement = fixture.nativeElement;
    const svg = el.querySelector('svg[role="img"]');
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute('aria-label')).toContain('Conservador 38 un');
    expect(el.querySelector('.forecast-ledger tbody')?.querySelectorAll('tr').length).toBe(2);
    expect(el.querySelector('.ceiling-title')?.textContent).toContain('Não utilizar como meta inicial');
    expect(el.querySelector('.ceiling-value')?.textContent).toContain('210 un/mês');
  });

  it('emite explainSimilar ao clicar em Explicar na lista de similares', () => {
    const emitted: string[] = [];
    component.explainSimilar.subscribe((ev) => emitted.push(ev.similar.sku));

    const btn: HTMLButtonElement = fixture.nativeElement.querySelector('.btn-explain');
    btn.click();

    expect(emitted).toEqual(['1042']);
  });
});
