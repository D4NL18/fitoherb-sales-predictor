/**
 * Cabeçalho do resultado com título-insight, linha de contexto e selo da data de referência (Design Plan §5.5).
 * Burro. O `h3` tem `tabindex="-1"` para receber o foco ao trocar de página (§7.3).
 */
import { Component, ElementRef, input, viewChild } from '@angular/core';
import { PtDatePipe } from '../../pipes/pt-br-format.pipes';

@Component({
  selector: 'app-query-context-header',
  standalone: true,
  imports: [PtDatePipe],
  templateUrl: './query-context-header.component.html',
  styleUrl: './query-context-header.component.scss',
})
export class QueryContextHeaderComponent {
  private readonly heading = viewChild.required<ElementRef<HTMLHeadingElement>>('heading');

  readonly title = input.required<string>();
  readonly subtitle = input<string>('');
  readonly dataReferencia = input<string | null>(null);

  /** Leva o foco ao título (paginação por teclado, §7.3). */
  focusHeading(): void {
    this.heading().nativeElement.focus();
  }
}
