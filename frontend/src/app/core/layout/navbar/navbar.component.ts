import { HttpClient } from '@angular/common/http';
import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { EMPTY, catchError } from 'rxjs';
import { PtDecimalPipe } from '../../../features/analytics/pipes/pt-br-format.pipes';
import { AnalyticsService } from '../../../features/analytics/services/analytics.service';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, PtDecimalPipe],
  templateUrl: './navbar.component.html',
  styleUrl: './navbar.component.scss',
})
export class NavbarComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);
  private readonly analyticsService = inject(HttpClient, { optional: true })
    ? inject(AnalyticsService, { optional: true })
    : null;

  readonly isMobileMenuOpen = signal<boolean>(false);
  readonly activeCatalogCount = signal<number | null>(null);

  ngOnInit(): void {
    if (!this.analyticsService) return;
    this.analyticsService
      .getCatalogProducts()
      .pipe(
        catchError(() => EMPTY),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((res) => {
        const count = res.meta?.totalItems ?? res.data?.length ?? null;
        if (typeof count === 'number' && Number.isFinite(count)) {
          this.activeCatalogCount.set(count);
        }
      });
  }

  toggleMobileMenu(): void {
    this.isMobileMenuOpen.update((v) => !v);
  }

  closeMobileMenu(): void {
    this.isMobileMenuOpen.set(false);
  }
}
