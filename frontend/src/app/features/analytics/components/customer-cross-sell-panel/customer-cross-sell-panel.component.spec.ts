/**
 * T-15 — Painel do modo cliente (F-10, F-11; Design Plan §5.7, §6).
 * Store mockado. O código do cliente só passa pelo store (LGPD-09): nada na URL nem em storage.
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CustomerCrossSellPanelComponent } from './customer-cross-sell-panel.component';
import { CrossSellStore } from '../../services/cross-sell.store';
import { AnalyticsService } from '../../services/analytics.service';
import { createFakeCrossSellStore, FakeCrossSellStore } from '../../testing/fake-cross-sell-store';
import {
  CONTRACT_MESSAGES,
  customerResponse,
  emptyCustomerResponse,
  inactiveCustomerResponse,
} from '../../testing/cross-sell-test-data';

describe('CustomerCrossSellPanelComponent', () => {
  let fixture: ComponentFixture<CustomerCrossSellPanelComponent>;
  let store: FakeCrossSellStore;
  let element: HTMLElement;

  beforeEach(async () => {
    store = createFakeCrossSellStore();
    store.mode.set('customer');
    await TestBed.configureTestingModule({
      imports: [CustomerCrossSellPanelComponent],
      providers: [
        { provide: CrossSellStore, useValue: store },
        { provide: AnalyticsService, useValue: jasmine.createSpyObj('AnalyticsService', ['getHealth']) },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(CustomerCrossSellPanelComponent);
    element = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
  });

  function render(): string {
    fixture.detectChanges();
    return element.textContent ?? '';
  }

  function submit(value: string): void {
    const input = element.querySelector('input') as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    (element.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    fixture.detectChanges();
  }

  it('estado inicial guia a consulta por cliente', () => {
    expect(render()).toContain('Escolha um cliente');
  });

  it('envia o código ao store sem gravar em storage', () => {
    const setItem = spyOn(Storage.prototype, 'setItem');
    submit('48213');

    expect(store.searchCustomer).toHaveBeenCalledOnceWith(48213);
    expect(setItem).not.toHaveBeenCalled();
  });

  it('rejeita código não numérico na tela', () => {
    submit('1 OR 1=1');
    expect(store.searchCustomer).not.toHaveBeenCalled();
    expect(render()).toContain('Digite só números, sem pontos ou letras.');
  });

  it('carregando: skeleton com aria-busy', () => {
    store.customer.status.set('loading');
    render();
    expect(element.querySelector('[aria-busy="true"]')).not.toBeNull();
  });

  it('sucesso: motivo e frase de motivo, sem margem nem números', () => {
    store.customer.status.set('success');
    store.customer.response.set(customerResponse());
    const text = render();

    expect(text).toContain('Nunca comprou');
    expect(text).toContain('Parou há 120 dias');
    expect(text).not.toContain('Custo estimado');
    expect(text).toContain('Sugerido porque o cliente compra CHA VERDE 100G. O cliente nunca comprou GENGIBRE EM PO 100G.');
    expect(text).not.toContain('Margem');
    expect(text).not.toContain('Ver números');
    expect(element.querySelectorAll('li').length).toBeGreaterThanOrEqual(2);
  });

  it('a ordem é a da API (G antes de B)', () => {
    store.customer.status.set('success');
    store.customer.response.set(customerResponse());
    const text = render();

    expect(text.indexOf('GENGIBRE EM PO 100G')).toBeLessThan(text.indexOf('CAPSULA DE HIBISCO'));
  });

  it('vazio comum (C-06) e vazio por falta de compras recentes (C-07) têm textos distintos', () => {
    store.customer.status.set('empty');
    store.customer.response.set(emptyCustomerResponse());
    const common = render();
    expect(common).toContain('Nada novo para oferecer');

    store.customer.response.set(inactiveCustomerResponse());
    const inactive = render();
    expect(inactive).toContain('não compra há mais de');
    expect(inactive).not.toContain('Nada novo para oferecer');
  });

  it('XSL-002 aparece inline no campo', () => {
    store.customer.status.set('error');
    store.customer.error.set({ code: 'XSL-002', message: CONTRACT_MESSAGES['XSL-002'], fields: [] });

    expect(render()).toContain('Cliente sem histórico de compras.');
    expect((element.querySelector('input') as HTMLInputElement).getAttribute('aria-invalid')).toBe('true');
  });

  it('XSL-003 mostra dados insuficientes; erro genérico mostra o banner', () => {
    store.customer.status.set('error');
    store.customer.error.set({ code: 'XSL-003', message: CONTRACT_MESSAGES['XSL-003'], fields: [] });
    expect(render()).toContain('Ainda não dá para recomendar com segurança');

    store.customer.error.set(null);
    render();
    expect(element.querySelector('[role="alert"]')?.textContent).toContain('Tentar de novo');
  });

  it('paginação no modo cliente', () => {
    store.customer.status.set('success');
    store.customer.response.set(customerResponse({ totalItems: 60, totalPages: 2 }));
    render();

    const next = Array.from(element.querySelectorAll('button')).find((button) =>
      (button.getAttribute('aria-label') ?? button.textContent ?? '').includes('Próxima'),
    ) as HTMLButtonElement | undefined;
    next?.click();
    expect(store.goToPage).toHaveBeenCalledOnceWith(2);
  });
});
