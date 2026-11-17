import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NewProductForecastRequest, NewProductOptions } from '../../../../models/new-product.model';
import { NewProductFormComponent } from './new-product-form.component';

const OPTIONS: NewProductOptions = {
  tipos: ['Capsulas', 'Tinturas'],
  fornecedores: ['FITOHERB LABORATORIOS', 'HERBAL BRASIL'],
};

describe('NewProductFormComponent', () => {
  let fixture: ComponentFixture<NewProductFormComponent>;
  let component: NewProductFormComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NewProductFormComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(NewProductFormComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('options', OPTIONS);
    fixture.detectChanges();
  });

  it('exibe skeleton enquanto optionsLoading = true', () => {
    fixture.componentRef.setInput('optionsLoading', true);
    fixture.detectChanges();

    const skeletons = fixture.nativeElement.querySelectorAll('.field-skeleton');
    expect(skeletons.length).toBe(2);
    expect(fixture.nativeElement.querySelector('select#np-tipo')).toBeNull();
  });

  it('converte margemMinimaDesejada de 0-100% para 0.00-1.00 e emite payload completo', () => {
    const submitted: NewProductForecastRequest[] = [];
    component.submitForecast.subscribe((req) => submitted.push(req));

    const select: HTMLSelectElement = fixture.nativeElement.querySelector('#np-tipo');
    select.value = 'Tinturas';
    select.dispatchEvent(new Event('change'));

    const supplierInput: HTMLInputElement = fixture.nativeElement.querySelector('#np-fornecedor');
    supplierInput.value = 'FITOHERB LABORATORIOS';
    supplierInput.dispatchEvent(new Event('input'));

    const descInput: HTMLInputElement = fixture.nativeElement.querySelector('#np-descricao');
    descInput.value = 'Tintura de Melissa 50ml';
    descInput.dispatchEvent(new Event('input'));

    const precoInput: HTMLInputElement = fixture.nativeElement.querySelector('#np-preco');
    precoInput.value = '42,50';
    precoInput.dispatchEvent(new Event('input'));

    const custoInput: HTMLInputElement = fixture.nativeElement.querySelector('#np-custo');
    custoInput.value = '19,10';
    custoInput.dispatchEvent(new Event('input'));

    const margemInput: HTMLInputElement = fixture.nativeElement.querySelector('#np-margem');
    margemInput.value = '35,0';
    margemInput.dispatchEvent(new Event('input'));

    fixture.detectChanges();

    const form: HTMLFormElement = fixture.nativeElement.querySelector('form');
    form.dispatchEvent(new Event('submit'));
    fixture.detectChanges();

    expect(submitted.length).toBe(1);
    expect(submitted[0]).toEqual({
      tipo: 'Tinturas',
      fornecedor: 'FITOHERB LABORATORIOS',
      descricao: 'Tintura de Melissa 50ml',
      precoVendaPrevisto: 42.5,
      custoUnitario: 19.1,
      margemMinimaDesejada: 0.35,
      horizonMonths: 3,
    });
  });

  it('bloqueia submit e exibe erro inline pt-BR quando custoUnitario > precoVendaPrevisto', () => {
    const submitted: NewProductForecastRequest[] = [];
    component.submitForecast.subscribe((req) => submitted.push(req));

    const select: HTMLSelectElement = fixture.nativeElement.querySelector('#np-tipo');
    select.value = 'Tinturas';
    select.dispatchEvent(new Event('change'));

    const supplierInput: HTMLInputElement = fixture.nativeElement.querySelector('#np-fornecedor');
    supplierInput.value = 'FITOHERB LABORATORIOS';
    supplierInput.dispatchEvent(new Event('input'));

    const descInput: HTMLInputElement = fixture.nativeElement.querySelector('#np-descricao');
    descInput.value = 'Tintura de Melissa 50ml';
    descInput.dispatchEvent(new Event('input'));

    const precoInput: HTMLInputElement = fixture.nativeElement.querySelector('#np-preco');
    precoInput.value = '30,00';
    precoInput.dispatchEvent(new Event('input'));

    const custoInput: HTMLInputElement = fixture.nativeElement.querySelector('#np-custo');
    custoInput.value = '35,00';
    custoInput.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const errorEl: HTMLElement | null = fixture.nativeElement.querySelector('#np-custo-error');
    expect(errorEl?.textContent).toContain('não pode ser maior que o preço de venda previsto');

    const form: HTMLFormElement = fixture.nativeElement.querySelector('form');
    form.dispatchEvent(new Event('submit'));
    expect(submitted.length).toBe(0);
  });

  it('permite custoUnitario == precoVendaPrevisto com aviso de margem 0,00% e avisa margem sem custo', () => {
    const precoInput: HTMLInputElement = fixture.nativeElement.querySelector('#np-preco');
    precoInput.value = '40,00';
    precoInput.dispatchEvent(new Event('input'));

    const custoInput: HTMLInputElement = fixture.nativeElement.querySelector('#np-custo');
    custoInput.value = '40,00';
    custoInput.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('#np-custo-hint')?.textContent).toContain('0,00%');

    custoInput.value = '';
    custoInput.dispatchEvent(new Event('input'));
    const margemInput: HTMLInputElement = fixture.nativeElement.querySelector('#np-margem');
    margemInput.value = '25';
    margemInput.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('#np-margem-hint')?.textContent).toContain('custo unitário');
  });

  it('limpa simulação ao clicar em Limpar simulação e emite resetSimulation', () => {
    let resetCount = 0;
    component.resetSimulation.subscribe(() => {
      resetCount += 1;
    });

    const descInput: HTMLInputElement = fixture.nativeElement.querySelector('#np-descricao');
    descInput.value = 'Produto teste';
    descInput.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const resetBtn: HTMLButtonElement = fixture.nativeElement.querySelector('.btn-reset');
    resetBtn.click();
    fixture.detectChanges();

    expect(resetCount).toBe(1);
    expect(descInput.value).toBe('');
  });
});
