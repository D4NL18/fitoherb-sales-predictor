import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NewProductForecastRequest, SimilarProductItem } from '../../../../models/new-product.model';
import { NewProductSimilarsDrawerComponent } from './new-product-similars-drawer.component';

const MOCK_SIMILAR: SimilarProductItem = {
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
};

const MOCK_SUMMARY: NewProductForecastRequest = {
  tipo: 'Tinturas',
  fornecedor: 'FITOHERB LABORATORIOS',
  descricao: 'Tintura de Melissa 50ml',
  precoVendaPrevisto: 42.5,
  horizonMonths: 3,
};

describe('NewProductSimilarsDrawerComponent', () => {
  let fixture: ComponentFixture<NewProductSimilarsDrawerComponent>;
  let component: NewProductSimilarsDrawerComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NewProductSimilarsDrawerComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(NewProductSimilarsDrawerComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('inputSummary', MOCK_SUMMARY);
    fixture.componentRef.setInput('similar', MOCK_SIMILAR);
    fixture.detectChanges();
  });

  it('renderiza dialog acessível com role=dialog, aria-modal=true e os 3 scores parciais', () => {
    const dialog: HTMLElement | null = fixture.nativeElement.querySelector('[role="dialog"]');
    expect(dialog).not.toBeNull();
    expect(dialog?.getAttribute('aria-modal')).toBe('true');

    const text = dialog?.textContent ?? '';
    expect(text).toContain('Descrição / Texto TF-IDF (peso 50%)');
    expect(text).toContain('Proximidade Log-Preço (peso 40%)');
    expect(text).toContain('Mesmo Fornecedor (peso 10%)');
    expect(text).toContain('Mesmo fornecedor');
  });

  it('fecha ao pressionar Escape e restaura foco ao botão gatilho', async () => {
    const trigger = document.createElement('button');
    document.body.appendChild(trigger);
    spyOn(trigger, 'focus');
    fixture.componentRef.setInput('returnFocusTo', trigger);

    let closed = 0;
    component.closeDrawer.subscribe(() => {
      closed += 1;
      fixture.componentRef.setInput('similar', null);
    });

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    fixture.detectChanges();
    await Promise.resolve();

    expect(closed).toBe(1);
    expect(trigger.focus).toHaveBeenCalled();
    trigger.remove();
  });

  it('mantém Focus Trap ao pressionar Tab/Shift+Tab dentro do dialog', () => {
    const closeBtn: HTMLButtonElement = fixture.nativeElement.querySelector('.drawer-close');
    closeBtn.focus();

    const tabEvent = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true });
    document.dispatchEvent(tabEvent);
    expect(tabEvent.defaultPrevented).toBeTrue();
    expect(document.activeElement).toBe(closeBtn);
  });
});
