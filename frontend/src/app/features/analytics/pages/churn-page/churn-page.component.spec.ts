import { HttpErrorResponse } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Subject, of, throwError } from 'rxjs';
import {
  ChurnCustomersResponse,
  CustomerChurnDetailResponse,
  InactiveChurnResponse,
} from '../../models/churn.model';
import { AnalyticsService } from '../../services/analytics.service';
import { ChurnPageComponent } from './churn-page.component';
import { buildChurnCsvContent, mapInactiveChurnRow, sanitizeCsvCell } from './churn-page.helpers';

describe('ChurnPageComponent', () => {
  let component: ChurnPageComponent;
  let fixture: ComponentFixture<ChurnPageComponent>;
  let analyticsServiceSpy: jasmine.SpyObj<AnalyticsService>;

  const mockActiveResponse: ChurnCustomersResponse = {
    data: {
      resumo: {
        totalEmRisco: 12,
        totalAlerta: 5,
        totalSaudavel: 30,
        totalInativos: 8,
        receitaMensalEmRisco: 50000,
      },
      items: [
        {
          customerCode: 1001,
          status: 'EM_RISCO',
          diasSemComprar: 70,
          gapTipico: 15,
          diasReferencia: 60,
          fatorTempo: 1.17,
          faturamentoMedioMensal: 50000,
          scorePrioridade: 58500,
          historicoCurto: false,
        },
        {
          customerCode: 1002,
          status: 'ALERTA',
          diasSemComprar: 31,
          gapTipico: 0,
          diasReferencia: 30,
          fatorTempo: 1.03,
          faturamentoMedioMensal: 10000,
          scorePrioridade: 10300,
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
      totalItems: 120,
      totalPages: 3,
    },
  };

  const mockInactiveResponse: InactiveChurnResponse = {
    data: {
      totalInativos: 8,
      items: [
        {
          customerCode: 9001,
          status: 'INATIVO_RECUPERACAO',
          diasSemComprar: 240,
          dataUltimoPedido: '2026-03-17',
          faturamentoMedioMensal: 4200,
          historicoCurto: true,
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
      totalItems: 8,
      totalPages: 1,
    },
  };

  const mockDetailResponse: CustomerChurnDetailResponse = {
    data: {
      customerCode: 1001,
      status: 'EM_RISCO',
      diasSemComprar: 70,
      dataUltimoPedido: '2026-09-02',
      gapTipico: 15,
      diasReferencia: 60,
      fatorTempo: 1.17,
      faturamentoMedioMensal: 50000,
      scorePrioridade: 58500,
      historicoCurto: false,
      variacaoReceitaTrimestralPct: -25,
      historicoMensal: [
        { anoMes: '2026-09', faturamentoLiquido: 18000, qtdPedidos: 2 },
        { anoMes: '2026-08', faturamentoLiquido: 22000, qtdPedidos: 3 },
      ],
      produtosPerdidos: [
        {
          sku: 201,
          descricao: 'PROPOLIS 30ML',
          fornecedor: 'APIS FLORA',
          faturamentoHistorico: 12000,
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
    analyticsServiceSpy.getChurnCustomers.and.returnValue(of(mockActiveResponse));
    analyticsServiceSpy.getCustomerChurnDetail.and.returnValue(of(mockDetailResponse));
    analyticsServiceSpy.getInactiveChurn.and.returnValue(of(mockInactiveResponse));

    await TestBed.configureTestingModule({
      imports: [ChurnPageComponent],
      providers: [{ provide: AnalyticsService, useValue: analyticsServiceSpy }],
    }).compileComponents();

    fixture = TestBed.createComponent(ChurnPageComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => {
    document.body.style.overflow = '';
    fixture.destroy();
  });

  it('deve inicializar, carregar EM_RISCO com dataReferencia e expor aria-live e paginação', () => {
    expect(component).toBeTruthy();
    expect(analyticsServiceSpy.getChurnCustomers).toHaveBeenCalledWith('EM_RISCO', {
      limit: 50,
      offset: 0,
    });
    expect(component.customers().length).toBe(2);
    expect(component.dataReferencia()).toBe('2026-11-12');
    expect(component.loading()).toBeFalse();

    const text = (fixture.nativeElement.textContent as string).replace(/\s+/g, ' ');
    expect(text).toContain('Pedidos até 12/11/2026');
    expect(text).toContain('0,0d');
    expect(fixture.nativeElement.querySelector('[aria-live="polite"]')).toBeTruthy();
    expect(fixture.nativeElement.querySelector('app-list-pager')).toBeTruthy();
  });

  it('deve alternar para TODOS e atualizar aria-pressed', () => {
    component.setFilter('TODOS');
    fixture.detectChanges();

    expect(component.statusFilter()).toBe('TODOS');
    expect(analyticsServiceSpy.getChurnCustomers).toHaveBeenCalledWith('TODOS', {
      limit: 50,
      offset: 0,
    });
    const pressedBtns = fixture.nativeElement.querySelectorAll('.filter-chip[aria-pressed="true"]');
    expect(pressedBtns.length).toBe(1);
    expect(pressedBtns[0].textContent).toContain('Todos os ativos');
  });

  it('deve consultar getInactiveChurn sem inventar scorePrioridade para INATIVO_RECUPERACAO', () => {
    component.setFilter('INATIVO_RECUPERACAO');
    fixture.detectChanges();

    expect(analyticsServiceSpy.getInactiveChurn).toHaveBeenCalledWith({ limit: 50, offset: 0 });
    expect(component.customers().length).toBe(1);
    expect(component.customers()[0].scorePrioridade).toBeNull();
    expect(component.customers()[0].dataUltimoPedido).toBe('2026-03-17');

    const text = (fixture.nativeElement.textContent as string).replace(/\s+/g, ' ');
    expect(text).toContain('17/03/2026');
  });

  it('deve cancelar requisição obsoleta via switchMap ao trocar filtros rapidamente (anti race condition)', () => {
    const alerta$ = new Subject<ChurnCustomersResponse>();
    const saudavel$ = new Subject<ChurnCustomersResponse>();

    analyticsServiceSpy.getChurnCustomers.and.callFake((status: string | null) => {
      if (status === 'ALERTA') return alerta$.asObservable();
      if (status === 'SAUDAVEL') return saudavel$.asObservable();
      return of(mockActiveResponse);
    });

    component.setFilter('ALERTA');
    expect(alerta$.observed).toBeTrue();

    component.setFilter('SAUDAVEL');
    expect(alerta$.observed).toBeFalse();
    expect(saudavel$.observed).toBeTrue();

    saudavel$.next({
      ...mockActiveResponse,
      data: {
        ...mockActiveResponse.data,
        items: [
          {
            ...mockActiveResponse.data.items[0],
            customerCode: 2020,
            status: 'SAUDAVEL',
          },
        ],
      },
    });
    fixture.detectChanges();

    expect(component.statusFilter()).toBe('SAUDAVEL');
    expect(component.customers()[0].customerCode).toBe(2020);
    expect(component.loading()).toBeFalse();
  });

  it('deve cancelar detalhe em voo no switchMap ao trocar cliente ou fechar drawer', () => {
    const firstDetail$ = new Subject<CustomerChurnDetailResponse>();
    const secondDetail$ = new Subject<CustomerChurnDetailResponse>();

    analyticsServiceSpy.getCustomerChurnDetail.and.callFake((code: number) =>
      code === 1001 ? firstDetail$.asObservable() : secondDetail$.asObservable(),
    );

    component.openCustomerDetail(component.customers()[0]);
    expect(firstDetail$.observed).toBeTrue();

    component.openCustomerDetail(component.customers()[1]);
    expect(firstDetail$.observed).toBeFalse();
    expect(secondDetail$.observed).toBeTrue();

    component.closeDrawer();
    expect(secondDetail$.observed).toBeFalse();
    expect(component.isDrawerOpen()).toBeFalse();
  });

  it('deve exibir erro amigável e permitir retry no drawer sem vazar detail técnico', () => {
    analyticsServiceSpy.getCustomerChurnDetail.and.returnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 503,
            error: {
              error: { code: 'ANL-001', message: 'Base indisponível', fields: [] },
              detail: 'SELECT * FROM internal_table failed',
            },
          }),
      ),
    );

    component.openCustomerDetail(component.customers()[0]);
    fixture.detectChanges();

    expect(component.drawerError()).toContain('Base de vendas indisponível');
    expect(component.drawerError()).not.toContain('SELECT');
    expect(component.drawerLoading()).toBeFalse();

    analyticsServiceSpy.getCustomerChurnDetail.and.returnValue(of(mockDetailResponse));
    component.retryCustomerDetail();
    fixture.detectChanges();

    expect(component.drawerError()).toBeNull();
    expect(component.selectedCustomer()?.customerCode).toBe(1001);
  });

  it('deve aplicar inert na página ao abrir o drawer pela linha e restaurar foco ao botão ao fechar', async () => {
    const rowButtons = fixture.nativeElement.querySelectorAll('.btn-row-detail') as NodeListOf<HTMLButtonElement>;
    const firstBtn = rowButtons[0];
    firstBtn.focus();
    firstBtn.click();
    fixture.detectChanges();
    await Promise.resolve();
    fixture.detectChanges();

    const pageContainer = fixture.nativeElement.querySelector('.churn-page-container') as HTMLElement;
    const closeBtn = fixture.nativeElement.querySelector('.close-btn') as HTMLButtonElement;
    expect(pageContainer.hasAttribute('inert')).toBeTrue();
    expect(component.isDrawerOpen()).toBeTrue();
    expect(document.activeElement).toBe(closeBtn);

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    fixture.detectChanges();
    await Promise.resolve();
    fixture.detectChanges();

    expect(component.isDrawerOpen()).toBeFalse();
    expect(pageContainer.hasAttribute('inert')).toBeFalse();
    expect(document.activeElement).toBe(firstBtn);
  });

  it('deve manter aria-busy, exibir erro seguro na lista e desabilitar Exportar CSV em erro/vazio', () => {
    analyticsServiceSpy.getChurnCustomers.and.returnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 500,
            error: { detail: 'Stacktrace PostgreSQL confidencial' },
          }),
      ),
    );

    component.setFilter('ALERTA');
    fixture.detectChanges();

    const text = (fixture.nativeElement.textContent as string) || '';
    expect(text).toContain('Não foi possível carregar a lista de churn.');
    expect(text).not.toContain('Stacktrace PostgreSQL');
    expect(component.customers().length).toBe(0);

    const exportBtn = fixture.nativeElement.querySelector('.btn-export') as HTMLButtonElement;
    expect(exportBtn.disabled).toBeTrue();

    component.exportCsv();
    expect(component.isExporting()).toBeFalse();
  });

  it('deve paginar via onPageChange mantendo o filtro atual', () => {
    component.onPageChange(2);
    expect(analyticsServiceSpy.getChurnCustomers).toHaveBeenCalledWith('EM_RISCO', {
      limit: 50,
      offset: 50,
    });
  });

  it('deve neutralizar Formula Injection e gerar CSV UTF-8 com BOM, ; e zero PII', () => {
    expect(sanitizeCsvCell('=CMD("calc")')).toBe('"\'=CMD(""calc"")"');
    expect(sanitizeCsvCell('+1+1')).toBe('"\'+1+1"');
    expect(sanitizeCsvCell('-50')).toBe('"\'-50"');
    expect(sanitizeCsvCell('@SUM(A1)')).toBe('"\'@SUM(A1)"');
    expect(sanitizeCsvCell('\t=2+2')).toBe('"\'\t=2+2"');
    expect(sanitizeCsvCell('\r+2+2')).toBe('"\'\r+2+2"');
    expect(sanitizeCsvCell('texto;com"aspas\nquebra')).toBe('"texto;com""aspas\nquebra"');

    const csvActive = buildChurnCsvContent(component.customers(), 'EM_RISCO');
    expect(csvActive.startsWith('\uFEFF')).toBeTrue();
    expect(csvActive).toContain('Codigo Cliente;Status;Dias Sem Comprar');
    expect(csvActive).toContain('1001;Em risco;70;15,0;60;Nao;50000,00;58500,00');
    expect(csvActive.toLowerCase()).not.toContain('cpf');
    expect(csvActive.toLowerCase()).not.toContain('cnpj');
    expect(csvActive.toLowerCase()).not.toContain('telefone');

    const inactiveRow = mapInactiveChurnRow(mockInactiveResponse.data.items[0]);
    const csvInactive = buildChurnCsvContent([inactiveRow], 'INATIVO_RECUPERACAO');
    expect(csvInactive).toContain('9001;Inativo antigo;240;17/03/2026;Sim;4200,00');
  });

  it('deve cumprir LGPD: nunca gravar customerCode na URL nem em localStorage/sessionStorage', () => {
    localStorage.clear();
    sessionStorage.clear();
    const consoleSpy = spyOn(console, 'log');

    component.openCustomerDetail(component.customers()[0]);
    fixture.detectChanges();

    expect(window.location.href).not.toContain('1001');
    expect(JSON.stringify(localStorage)).not.toContain('1001');
    expect(JSON.stringify(sessionStorage)).not.toContain('1001');
    expect(consoleSpy).not.toHaveBeenCalled();
  });
});
