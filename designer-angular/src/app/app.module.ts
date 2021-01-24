import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { HttpClientModule } from '@angular/common/http';

import { RouterModule, Routes } from '@angular/router';
import { AppComponent } from './app.component';
import { PipelineComponent } from './pipeline/pipeline.component';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';

import { MatToolbarModule } from '@angular/material/toolbar';
import { MatIconModule} from '@angular/material/icon';
import { MatSidenavModule} from '@angular/material/sidenav';
import { MatListModule} from '@angular/material/list';
import { MatButtonModule} from '@angular/material/button';


const routes: Routes = [
  {
    path: 'pipeline', component: PipelineComponent,
  }
  /*
  {
    path: 'tail', component: MsgTailerComponent,
  },
  {
    path: 'dash', component: DashComponent,
  },
  {
    path: '', component: MainMenuComponent
  }*/
];

@NgModule({
  declarations: [
    AppComponent,
    PipelineComponent,
    /*
    MsgTailerComponent,
    MainMenuComponent,
    DashComponent*/
  ],
  imports: [
    BrowserModule,
    HttpClientModule,
    RouterModule.forRoot(routes),
    BrowserAnimationsModule,
    HttpClientModule,
    MatToolbarModule,
    MatSidenavModule,
    MatListModule,
    MatButtonModule,
    MatIconModule
  ],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule { }
