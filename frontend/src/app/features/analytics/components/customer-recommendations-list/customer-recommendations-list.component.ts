/**
 * Lista priorizada do modo cliente (Design Plan §5.7; F-10; P-062 a P-065).
 * Burro: ordem da API (pontuação, P-064.2). Na página 1, as `PRIORITY_COUNT` primeiras ficam numa lista
 * "Prioridade" e as demais em "Outras sugestões" (D-9, hit rate@5 de P-071). Só o código do cliente existe na tela.
 */
import { Component, computed, input } from '@angular/core';
import { CustomerRecommendationItem } from '../../models/cross-sell.model';
import { ListPositionPipe } from '../../pipes/pt-br-format.pipes';
import { relatedAntecedentsNote } from '../../utils/cross-sell-view';

/** Quantas sugestões recebem destaque de prioridade na primeira página (D-9, P-071). */
export const PRIORITY_COUNT = 5;

/** Bloco de linhas renderizado como uma `<ol>` própria. */
interface RecommendationGroup {
  label: string;
  start: number;
  highlighted: boolean;
  items: CustomerRecommendationItem[];
}

@Component({
  selector: 'app-customer-recommendations-list',
  standalone: true,
  imports: [ListPositionPipe],
  templateUrl: './customer-recommendations-list.component.html',
  styleUrl: '../../styles/recommendation-list.scss',
})
export class CustomerRecommendationsListComponent {
  readonly items = input.required<CustomerRecommendationItem[]>();
  readonly pageOffset = input<number>(0);

  protected readonly groups = computed<RecommendationGroup[]>(() => {
    const items = this.items();
    const offset = this.pageOffset();
    if (offset > 0) return [{ label: 'Sugestões', start: offset + 1, highlighted: false, items }];

    const groups: RecommendationGroup[] = [
      { label: `Prioridade: ${PRIORITY_COUNT} primeiras sugestões`, start: 1, highlighted: true, items: items.slice(0, PRIORITY_COUNT) },
    ];
    if (items.length > PRIORITY_COUNT) {
      groups.push({ label: 'Outras sugestões', start: PRIORITY_COUNT + 1, highlighted: false, items: items.slice(PRIORITY_COUNT) });
    }
    return groups;
  });

  protected relatedNote(item: CustomerRecommendationItem): string | null {
    return relatedAntecedentsNote(item.qtdAntecedentesRelacionados);
  }
}
