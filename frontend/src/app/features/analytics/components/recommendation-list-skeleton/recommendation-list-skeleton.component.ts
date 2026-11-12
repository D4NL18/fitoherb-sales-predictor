/**
 * Skeleton da lista de sugestões com a geometria real das linhas (Design Plan §6.2).
 * Sem spinner isolado. Se a busca passar de `SLOW_QUERY_NOTICE_MS`, mostra o aviso honesto de primeira
 * consulta lenta (cache frio, P-068) numa região viva própria; as barras são `aria-hidden`.
 */
import { Component, OnDestroy, OnInit, input, signal } from '@angular/core';
import { COLD_CACHE_NOTICE } from '../../utils/cross-sell-view';

/** Tempo de espera antes de avisar que a primeira consulta demora (§6.2). */
export const SLOW_QUERY_NOTICE_MS = 4000;
const DEFAULT_SKELETON_ROWS = 5;

@Component({
  selector: 'app-recommendation-list-skeleton',
  standalone: true,
  templateUrl: './recommendation-list-skeleton.component.html',
  styleUrl: './recommendation-list-skeleton.component.scss',
})
export class RecommendationListSkeletonComponent implements OnInit, OnDestroy {
  readonly rows = input<number>(DEFAULT_SKELETON_ROWS);
  readonly showHeader = input<boolean>(true);

  protected readonly slowNoticeVisible = signal(false);
  protected readonly slowNotice = COLD_CACHE_NOTICE;
  private slowTimer: ReturnType<typeof setTimeout> | null = null;

  protected rowIndexes(): number[] {
    return Array.from({ length: this.rows() }, (_, index) => index);
  }

  ngOnInit(): void {
    this.slowTimer = setTimeout(() => this.slowNoticeVisible.set(true), SLOW_QUERY_NOTICE_MS);
  }

  ngOnDestroy(): void {
    if (this.slowTimer !== null) clearTimeout(this.slowTimer);
  }
}
