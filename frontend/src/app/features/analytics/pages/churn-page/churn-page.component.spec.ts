import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { ChurnPageComponent } from './churn-page.component';
import { AnalyticsService } from '../../services/analytics.service';
import { ChurnCustomersResponse, CustomerChurnDetailResponse } from '../../models/churn.model';

describe('ChurnPageComponent', () => {
  let component: ChurnPageComponent;
  let fixture: ComponentFixture<ChurnPageComponent>;
  let analyticsServiceSpy: jasmine.SpyObj<AnalyticsService>;

  const mockResponse: ChurnCustomersResponse = {
    data: {
      resumo: {
        totalEmRisco: 1,
        totalAlerta: 0,
        totalSaudavel: 0,
        totalInativos: 0,
        receitaMensalEmRisco: 50000.0,
      },
      items: [
        {
          customerCode: 1001,
          status: 'EM_RISCO',
          diasSemComprar: 70,
          gapTipico: 15.0,
          diasReferencia: 60,
          fatorTempo: 1.17,
          faturamentoMedioMensal: 50000.0,
          scorePrioridade: 58500.0,
          historicoCurto: false,
        },
      ],
    },
    meta: {
      timestamp: '2026-11-12T12:00:00Z',
      version: '1.0.0',
      dataReferencia: '2026-11-12',
      page: 1,
      limit: 50,
      offset: 0,
      totalItems: 1,
      totalPages: 1,
    },
  };

  const mockDetailResponse: CustomerChurnDetailResponse = {
    data: {
      customerCode: 1001,
      status: 'EM_RISCO',
      diasSemComprar: 70,
      dataUltimoPedido: '2026-09-02',
      gapTipico: 15.0,
      diasReferencia: 60,
      fatorTempo: 1.17,
      faturamentoMedioMensal: 50000.0,
      scorePrioridade: 58500.0,
      historicoCurto: false,
      variacaoReceitaTrimestralPct: -25.0,
      historicoMensal: [],
      produtosPerdidos: [
        {
          sku: 201,
          descricao: 'PROPOLIS 30ML',
          fornecedor: 'APIS FLORA',
          faturamentoHistorico: 12000.0,
          dataUltimaCompra: '2026-07-10',
        },
      ],
    },
    meta: {
      timestamp: '2026-11-12T12:00:00Z',
      version: '1.0.0',
      dataReferencia: '2026-11-12',
    },
  };

  beforeEach(async () => {
    analyticsServiceSpy = jasmine.createSpyObj('AnalyticsService', [
      'getChurnCustomers',
      'getCustomerChurnDetail',
      'getInactiveChurn',
    ]);
    analyticsServiceSpy.getChurnCustomers.and.returnValue(of(mockResponse));
    analyticsServiceSpy.getCustomerChurnDetail.and.returnValue(of(mockDetailResponse));

    await TestBed.configureTestingModule({
      imports: [ChurnPageComponent],
      providers: [{ provide: AnalyticsService, useValue: analyticsServiceSpy }],
    }).compileComponents();

    fixture = TestBed.createComponent(ChurnPageComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('deve inicializar o componente e carregar dados de clientes em risco', () => {
    expect(component).toBeTruthy();
    expect(analyticsServiceSpy.getChurnCustomers).toHaveBeenCalledWith('EM_RISCO', { limit: 50, offset: 0 });
    expect(component.customers().length).toBe(1);
    expect(component.customers()[0].customerCode).toBe(1001);
    expect(component.resumo()?.totalEmRisco).toBe(1);
    expect(component.loading()).toBeFalse();
  });

  it('deve alternar filtro para ALERTA e disparar nova busca', () => {
    component.setFilter('ALERTA');
    expect(component.statusFilter()).toBe('ALERTA');
    expect(analyticsServiceSpy.getChurnCustomers).toHaveBeenCalledWith('ALERTA', { limit: 50, offset: 0 });
  });

  it('deve abrir o drawer de diagnóstico ao selecionar um cliente', () => {
    component.openCustomerDetail(component.customers()[0]);
    expect(component.isDrawerOpen()).toBeTrue();
    expect(analyticsServiceSpy.getCustomerChurnDetail).toHaveBeenCalledWith(1001);
    expect(component.selectedCustomer()?.customerCode).toBe(1001);
  });

  it('deve fechar o drawer ao chamar closeDrawer', () => {
    component.isDrawerOpen.set(true);
    component.closeDrawer();
    expect(component.isDrawerOpen()).toBeFalse();
    expect(component.selectedCustomer()).toBeNull();
  });
});
