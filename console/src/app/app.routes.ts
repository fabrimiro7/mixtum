import { Routes } from '@angular/router';

import { LoginComponent } from './modules/auth/components/login/login.component';
import { DashboardComponent } from './modules/dashboard/components/dashboard/dashboard.component';
import { AdministrationComponent } from './modules/administration/administration.component';
import { MainLayoutComponent } from './layout/main-layout/main-layout.component';
import { authGuard } from './core/guards/auth.guard';
import { consolePlugins } from '../instance/plugins';

export const routes: Routes = [

  {
    path: 'login',
    component: LoginComponent
  },
  {
    path: '',
    component: MainLayoutComponent,
    canActivate: [authGuard],
    children: [
      {
        path: '',
        redirectTo: 'dashboard',
        pathMatch: 'full'
      },
      {
        path: 'dashboard',
        component: DashboardComponent
      },
      {
        path: 'administration',
        component: AdministrationComponent
      },
      ...consolePlugins.flatMap(plugin => plugin.routes),
    ]
  },

  { path: '**', redirectTo: '/' }

];
