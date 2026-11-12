import { Component, EventEmitter, Input, Output, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CustomerChurnDetailData } from '../../models/churn.model';

@Component({
  selector: 'app-customer-churn-drawer',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './customer-churn-drawer.component.html',
  styleUrl: './customer-churn-drawer.component.scss',
})
export class CustomerChurnDrawerComponent {
  @Input() customer: CustomerChurnDetailData | null = null;
  @Input() isOpen = false;
  @Input() loading = false;
  @Output() closeDrawer = new EventEmitter<void>();

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.isOpen) {
      this.close();
    }
  }

  close(): void {
    this.closeDrawer.emit();
  }

  formatCurrency(value: number): string {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
  }

  formatDate(dateStr: string | null): string {
    if (!dateStr) return '—';
    const [year, month, day] = dateStr.split('-');
    return `${day}/${month}/${year}`;
  }
}
