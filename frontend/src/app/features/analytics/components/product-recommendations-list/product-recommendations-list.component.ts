/**
 * Lista ranqueada do modo produto (Design Plan §5.6; F-09; P-061, P-065, A-8).
 * Burro: mantém a ordem da API, não esmaece nem reordena itens sinalizados (D-8). As frases vêm prontas
 * do backend; a frase de intensidade vira chip com o texto completo para leitor de tela.
 */
import { Component, input } from '@angular/core';
import { ProductRecommendationItem } from '../../models/cross-sell.model';
import { ListPositionPipe, PtDecimalPipe } from '../../pipes/pt-br-format.pipes';

/** Casas do lift no chip "▲ 4,3× mais que o normal" (mesma regra da frase P-065.2). */
const CHIP_LIFT_DIGITS = 1;
const PERCENT_SCALE = 100;

@Component({
  selector: 'app-product-recommendations-list',
  standalone: true,
  imports: [PtDecimalPipe, ListPositionPipe],
  templateUrl: './product-recommendations-list.component.html',
  styleUrl: '../../styles/recommendation-list.scss',
})
export class ProductRecommendationsListComponent {
  readonly items = input.required<ProductRecommendationItem[]>();
  /** `offset` da página, para numerar a posição na lista completa. */
  readonly pageOffset = input<number>(0);
  readonly label = input<string>('Sugestões para o produto');

  protected readonly chipLiftDigits = CHIP_LIFT_DIGITS;
  protected readonly percentScale = PERCENT_SCALE;
}
