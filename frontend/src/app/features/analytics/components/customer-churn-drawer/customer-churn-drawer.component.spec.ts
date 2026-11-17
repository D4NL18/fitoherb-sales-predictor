import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CustomerChurnDetailData } from '../../models/churn.model';
import { CustomerChurnDrawerComponent } from './customer-churn-drawer.component';

@Component({
  standalone: true,
  imports: [CustomerChurnDrawerComponent],
  template: `
    <button #opener type="button" id="opener-btn" (click)="open()">Abrir</button>
    <app-customer-churn-drawer
      [customer]="customer"
      [customerCode]="customerCode"
      [isOpen]="isOpen"
      [loading]="loading"
      [error]="error"
      [returnFocusTo]="opener"
      (closeDrawer)="onClose()"
      (retry)="retryCount = retryCount + 1"
    />
  `,
})
class DrawerHostComponent {
  customer: CustomerChurnDetailData | null = null;
  customerCode: number | null = 1001;
  isOpen = false;
  loading = false;
  error: string | null = null;
  closeCount = 0;
  retryCount = 0;

  open(): void {
    this.isOpen = true;
  }

  onClose(): void {
    this.closeCount += 1;
    this.isOpen = false;
  }
}

describe('CustomerChurnDrawerComponent', () => {
  let fixture: ComponentFixture<DrawerHostComponent>;
  let host: DrawerHostComponent;

  const mockDetail: CustomerChurnDetailData = {
    customerCode: 1001,
    status: 'EM_RISCO',
    diasSemComprar: 45,
    dataUltimoPedido: '2026-09-28',
    gapTipico: 0,
    diasReferencia: 30,
    fatorTempo: 1.5,
    faturamentoMedioMensal: 12000,
    scorePrioridade: 18000,
    historicoCurto: false,
    variacaoReceitaTrimestralPct: -25.4,
    historicoMensal: [
      { anoMes: '2026-10', faturamentoLiquido: 5000, qtdPedidos: 1 },
      { anoMes: '2026-08', faturamentoLiquido: 10000, qtdPedidos: 3 },
      { anoMes: '2026-09', faturamentoLiquido: 7500, qtdPedidos: 2 },
    ],
    produtosPerdidos: [
      {
        sku: 305,
        descricao: 'CHÁ VERDE 100G',
        fornecedor: 'CATARINENSE',
        faturamentoHistorico: 4200,
        dataUltimaCompra: '2026-07-15',
      },
    ],
  };

  beforeEach(async () => {
    document.body.style.overflow = '';
    await TestBed.configureTestingModule({
      imports: [DrawerHostComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(DrawerHostComponent);
    host = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => {
    document.body.style.overflow = '';
    fixture.destroy();
  });

  it('deve manter aria-hidden e inert enquanto o drawer estiver fechado', () => {
    const aside = fixture.nativeElement.querySelector('aside.churn-drawer') as HTMLElement;
    expect(aside.getAttribute('role')).toBe('dialog');
    expect(aside.getAttribute('aria-modal')).toBe('true');
    expect(aside.getAttribute('aria-labelledby')).toBe('drawer-title');
    expect(aside.getAttribute('aria-hidden')).toBe('true');
    expect(aside.hasAttribute('inert')).toBeTrue();
  });

  it('deve bloquear scroll do body, mover foco inicial e restaurar foco ao fechar', async () => {
    const opener = fixture.nativeElement.querySelector('#opener-btn') as HTMLButtonElement;
    opener.focus();
    expect(document.activeElement).toBe(opener);

    host.customer = mockDetail;
    host.isOpen = true;
    fixture.detectChanges();
    await Promise.resolve();
    fixture.detectChanges();

    expect(document.body.style.overflow).toBe('hidden');
    const closeBtn = fixture.nativeElement.querySelector('.close-btn') as HTMLButtonElement;
    expect(document.activeElement).toBe(closeBtn);

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    fixture.detectChanges();
    await Promise.resolve();
    fixture.detectChanges();

    expect(host.closeCount).toBe(1);
    expect(document.body.style.overflow).toBe('');
    expect(document.activeElement).toBe(opener);
  });

  it('deve prender Tab e Shift+Tab dentro do drawer (Focus Trap)', async () => {
    host.customer = mockDetail;
    host.isOpen = true;
    fixture.detectChanges();
    await Promise.resolve();
    fixture.detectChanges();

    const closeBtn = fixture.nativeElement.querySelector('.close-btn') as HTMLButtonElement;
    const footerCloseBtn = fixture.nativeElement.querySelector('.btn-drawer-close') as HTMLButtonElement;

    footerCloseBtn.focus();
    const forwardTab = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
    document.dispatchEvent(forwardTab);
    expect(forwardTab.defaultPrevented).toBeTrue();
    expect(document.activeElement).toBe(closeBtn);

    const backwardTab = new KeyboardEvent('keydown', {
      key: 'Tab',
      shiftKey: true,
      bubbles: true,
      cancelable: true,
    });
    document.dispatchEvent(backwardTab);
    expect(backwardTab.defaultPrevented).toBeTrue();
    expect(document.activeElement).toBe(footerCloseBtn);
  });

  it('deve fechar ao clicar no backdrop', () => {
    host.isOpen = true;
    host.loading = true;
    fixture.detectChanges();

    const aside = fixture.nativeElement.querySelector('aside.churn-drawer') as HTMLElement;
    expect(aside.getAttribute('aria-busy')).toBe('true');

    const backdrop = fixture.nativeElement.querySelector('.drawer-backdrop') as HTMLElement;
    backdrop.click();
    expect(host.closeCount).toBe(1);
  });

  it('deve exibir estado de erro com role=alert e emitir retry ao clicar em Tentar novamente', () => {
    host.isOpen = true;
    host.error = 'Base de vendas indisponível no momento.';
    fixture.detectChanges();

    const alertBox = fixture.nativeElement.querySelector('.drawer-error[role="alert"]') as HTMLElement;
    expect(alertBox).toBeTruthy();
    expect(alertBox.textContent).toContain('Base de vendas indisponível');

    const retryBtn = fixture.nativeElement.querySelector('.btn-retry') as HTMLButtonElement;
    retryBtn.click();
    expect(host.retryCount).toBe(1);
  });

  it('deve exibir gapTipico=0 corretamente, ordenar histórico mensal e formatar variação trimestral sem multiplicar por 100', () => {
    host.customer = mockDetail;
    host.isOpen = true;
    fixture.detectChanges();

    const text = (fixture.nativeElement.textContent as string).replace(/\s+/g, ' ');
    expect(text).toContain('0,0 dias (régua 30d)');
    expect(text).toContain('▼');
    expect(text).toContain('-25,4%');
    expect(text).not.toContain('2.540');

    const monthLabels = Array.from(
      fixture.nativeElement.querySelectorAll('.history-month') as NodeListOf<HTMLElement>,
    ).map((el) => el.textContent?.trim());
    expect(monthLabels).toEqual(['08/2026', '09/2026', '10/2026']);
    expect(text).toContain('CHÁ VERDE 100G');
  });

  it('deve restaurar overflow do body mesmo se destruído enquanto aberto', () => {
    host.isOpen = true;
    fixture.detectChanges();
    expect(document.body.style.overflow).toBe('hidden');

    fixture.destroy();
    expect(document.body.style.overflow).toBe('');
  });
});
