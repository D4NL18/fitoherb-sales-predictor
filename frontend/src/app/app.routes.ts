import { Routes } from '@angular/router';
import { PricingPageComponent } from './features/pricing/pages/pricing-page/pricing-page.component';
import { InventoryPageComponent } from './features/inventory/pages/inventory-page/inventory-page.component';

export const routes: Routes = [
  { path: '', redirectTo: 'pricing', pathMatch: 'full' },
  { path: 'pricing', component: PricingPageComponent },
  { path: 'inventory', component: InventoryPageComponent },
  { path: '**', redirectTo: 'pricing' }
];

