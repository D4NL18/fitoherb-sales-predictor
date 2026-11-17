import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { InfoHelpCoordinatorService } from './info-help-coordinator.service';
import { InfoHelpComponent, InfoHelpContent } from './info-help.component';

function normalizeText(value: string | null | undefined): string {
  return (value ?? '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
}

const SAMPLE_CONTENT: InfoHelpContent = {
  title: 'Sensibilidade ao preço',
  whatIs: 'Mostra o quanto as vendas costumam mudar quando o preço sobe ou cai.',
  howToAnalyze: 'Valores abaixo de -1,00 indicam clientes muito sensíveis ao preço.',
  insight: 'Teste pequenos aumentos onde a sensibilidade for baixa e proteja margem.',
};

const SAMPLE_CONTENT_WITH_TECH: InfoHelpContent = {
  ...SAMPLE_CONTENT,
  technicalNote: 'Coeficiente Beta estimado por regressão log-log ponderada.',
};

@Component({
  standalone: true,
  imports: [InfoHelpComponent],
  template: `
    <div class="host-wrapper">
      <button type="button" class="outside-target">Elemento externo</button>

      <app-info-help
        class="first-help"
        topicLabel="Sensibilidade ao preço"
        [content]="firstContent()"
        size="sm"
        preferredAlign="start"
      />

      <app-info-help
        class="second-help"
        topicLabel="Lucro bruto estimado"
        [content]="secondContent()"
        size="md"
        preferredAlign="end"
      />
    </div>
  `,
})
class InfoHelpHostComponent {
  readonly firstContent = signal<InfoHelpContent>(SAMPLE_CONTENT);
  readonly secondContent = signal<InfoHelpContent>({
    title: 'Lucro bruto estimado',
    whatIs: 'Diferença entre o preço de venda e o custo multiplicada pelo volume previsto.',
    howToAnalyze: 'Compare o lucro projetado com o cenário atual antes de decidir.',
    insight: 'Faturar mais nem sempre significa lucrar mais; priorize a margem total.',
    technicalNote: 'Margem de Contribuição = (Preço Projetado - Custo) × Volume Projetado.',
  });
}

describe('InfoHelpCoordinatorService', () => {
  let service: InfoHelpCoordinatorService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(InfoHelpCoordinatorService);
  });

  it('mantém activeHelpId nulo inicialmente e controla abertura, troca e fechamento por id', () => {
    // Arrange
    expect(service.activeHelpId()).toBeNull();

    // Act
    service.open('help-1');

    // Assert
    expect(service.activeHelpId()).toBe('help-1');

    // Act: abrir outro substitui o ativo
    service.open('help-2');

    // Assert
    expect(service.activeHelpId()).toBe('help-2');

    // Act: fechar com id antigo não fecha o atual
    service.close('help-1');
    expect(service.activeHelpId()).toBe('help-2');

    // Act: fechar com id atual limpa
    service.close('help-2');
    expect(service.activeHelpId()).toBeNull();
  });

  it('alterna estado com toggle(id) e fecha qualquer ativo com close() sem argumentos', () => {
    // Arrange & Act
    service.toggle('help-a');
    expect(service.activeHelpId()).toBe('help-a');

    // Act: toggle no mesmo id fecha
    service.toggle('help-a');
    expect(service.activeHelpId()).toBeNull();

    // Act: toggle em novo id abre e close() global limpa
    service.toggle('help-b');
    expect(service.activeHelpId()).toBe('help-b');
    service.close();

    // Assert
    expect(service.activeHelpId()).toBeNull();
  });
});

describe('InfoHelpComponent', () => {
  let coordinator: InfoHelpCoordinatorService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [InfoHelpComponent, InfoHelpHostComponent],
    }).compileComponents();
    coordinator = TestBed.inject(InfoHelpCoordinatorService);
    coordinator.close();
  });

  function createSingleFixture(content: InfoHelpContent = SAMPLE_CONTENT): ComponentFixture<InfoHelpComponent> {
    const fixture = TestBed.createComponent(InfoHelpComponent);
    fixture.componentRef.setInput('topicLabel', 'Sensibilidade ao preço');
    fixture.componentRef.setInput('content', content);
    fixture.detectChanges();
    return fixture;
  }

  function createHostFixture(): ComponentFixture<InfoHelpHostComponent> {
    const fixture = TestBed.createComponent(InfoHelpHostComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('renderiza gatilho acessível com aria-label, aria-expanded="false" e aria-controls', () => {
    // Arrange & Act
    const fixture = createSingleFixture();
    const root = fixture.nativeElement as HTMLElement;
    const trigger = root.querySelector<HTMLButtonElement>('button[aria-label^="Ajuda sobre "]');

    // Assert
    expect(trigger).not.toBeNull();
    expect(trigger!.getAttribute('aria-label')).toBe('Ajuda sobre Sensibilidade ao preço');
    expect(trigger!.getAttribute('aria-expanded')).toBe('false');
    expect(trigger!.getAttribute('aria-controls')).toBeTruthy();
    expect(root.querySelector('[role="dialog"]')).toBeNull();
  });

  it('abre e fecha ao clicar e exibe O que é, Como analisar, Qual insight tirar e Detalhe técnico condicional', () => {
    // Arrange
    const fixture = createSingleFixture(SAMPLE_CONTENT);
    const root = fixture.nativeElement as HTMLElement;
    const trigger = root.querySelector<HTMLButtonElement>('button[aria-label^="Ajuda sobre "]')!;
    const controlsId = trigger.getAttribute('aria-controls');

    // Act: abrir
    trigger.click();
    fixture.detectChanges();

    // Assert: aberto sem technicalNote
    const dialog = root.querySelector<HTMLElement>('[role="dialog"]');
    expect(dialog).not.toBeNull();
    expect(dialog!.id).toBe(controlsId!);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');

    const text = normalizeText(dialog!.textContent);
    expect(text).toContain(SAMPLE_CONTENT.title);
    expect(text).toContain('O que é');
    expect(text).toContain(SAMPLE_CONTENT.whatIs);
    expect(text).toContain('Como analisar');
    expect(text).toContain(SAMPLE_CONTENT.howToAnalyze);
    expect(text).toContain('Qual insight tirar');
    expect(text).toContain(SAMPLE_CONTENT.insight);
    expect(text).not.toContain('Detalhe técnico');

    // Act: atualizar com technicalNote
    fixture.componentRef.setInput('content', SAMPLE_CONTENT_WITH_TECH);
    fixture.detectChanges();

    // Assert: exibe detalhe técnico condicional
    const updatedText = normalizeText(root.querySelector('[role="dialog"]')?.textContent);
    expect(updatedText).toContain('Detalhe técnico');
    expect(updatedText).toContain(SAMPLE_CONTENT_WITH_TECH.technicalNote!);

    // Act: clicar novamente fecha
    trigger.click();
    fixture.detectChanges();

    // Assert: fechado
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(root.querySelector('[role="dialog"]')).toBeNull();
  });

  it('garante no máximo 1 popover aberto simultaneamente entre duas instâncias', () => {
    // Arrange
    const fixture = createHostFixture();
    const root = fixture.nativeElement as HTMLElement;
    const firstTrigger = root.querySelector<HTMLButtonElement>('.first-help button[aria-label^="Ajuda sobre "]')!;
    const secondTrigger = root.querySelector<HTMLButtonElement>('.second-help button[aria-label^="Ajuda sobre "]')!;

    // Act: abre o primeiro
    firstTrigger.click();
    fixture.detectChanges();

    // Assert
    expect(root.querySelectorAll('[role="dialog"]').length).toBe(1);
    expect(firstTrigger.getAttribute('aria-expanded')).toBe('true');
    expect(secondTrigger.getAttribute('aria-expanded')).toBe('false');

    // Act: abre o segundo
    secondTrigger.click();
    fixture.detectChanges();

    // Assert: primeiro fechou automaticamente e só há 1 dialog aberto
    const dialogs = root.querySelectorAll('[role="dialog"]');
    expect(dialogs.length).toBe(1);
    expect(firstTrigger.getAttribute('aria-expanded')).toBe('false');
    expect(secondTrigger.getAttribute('aria-expanded')).toBe('true');
    expect(normalizeText(dialogs[0].textContent)).toContain('Lucro bruto estimado');
  });

  it('fecha ao pressionar Escape devolvendo o foco ao botão gatilho', () => {
    // Arrange
    const fixture = createHostFixture();
    const root = fixture.nativeElement as HTMLElement;
    const trigger = root.querySelector<HTMLButtonElement>('.first-help button[aria-label^="Ajuda sobre "]')!;

    trigger.focus();
    trigger.click();
    fixture.detectChanges();
    expect(root.querySelector('[role="dialog"]')).not.toBeNull();

    // Act
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    fixture.detectChanges();

    // Assert
    expect(root.querySelector('[role="dialog"]')).toBeNull();
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(trigger);
  });

  it('fecha ao clicar fora sem fechar quando o clique ocorre dentro do próprio diálogo', () => {
    // Arrange
    const fixture = createHostFixture();
    const root = fixture.nativeElement as HTMLElement;
    const trigger = root.querySelector<HTMLButtonElement>('.first-help button[aria-label^="Ajuda sobre "]')!;
    const outsideEl = root.querySelector<HTMLButtonElement>('.outside-target')!;

    trigger.click();
    fixture.detectChanges();
    const dialog = root.querySelector<HTMLElement>('[role="dialog"]')!;
    expect(dialog).not.toBeNull();

    // Act: clique interno preserva aberto
    dialog.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
    dialog.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    fixture.detectChanges();
    expect(root.querySelector('[role="dialog"]')).not.toBeNull();

    // Act: clique fora fecha
    outsideEl.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
    outsideEl.click();
    fixture.detectChanges();

    // Assert
    expect(root.querySelector('[role="dialog"]')).toBeNull();
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
  });

  it('renderiza payloads potencialmente maliciosos como texto literal sem criar nós HTML (anti-XSS)', () => {
    // Arrange
    const xssPayload: InfoHelpContent = {
      title: 'Título <img src=x onerror=alert(1)>',
      whatIs: '<script>alert(1)</script>',
      howToAnalyze: '<b>html</b>',
      insight: '<svg onload=alert(1)>insight</svg>',
      technicalNote: '<i>nota</i>',
    };
    const fixture = createSingleFixture(xssPayload);
    const root = fixture.nativeElement as HTMLElement;
    const trigger = root.querySelector<HTMLButtonElement>('button[aria-label^="Ajuda sobre "]')!;

    // Act
    trigger.click();
    fixture.detectChanges();

    // Assert
    const dialog = root.querySelector<HTMLElement>('[role="dialog"]')!;
    expect(dialog).not.toBeNull();
    expect(dialog.querySelectorAll('script, b, i, img').length).toBe(0);

    const text = dialog.textContent ?? '';
    expect(text).toContain('<script>alert(1)</script>');
    expect(text).toContain('<b>html</b>');
    expect(text).toContain('<i>nota</i>');
    expect(text).toContain('<img src=x onerror=alert(1)>');
  });
});
