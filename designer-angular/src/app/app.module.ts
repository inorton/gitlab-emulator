import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { HttpClientModule } from '@angular/common/http';

import { RouterModule, Routes } from '@angular/router';
import { AppComponent } from './app.component';
import { PipelineComponent } from './pipeline/pipeline.component';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';

import { NgbModule } from '@ng-bootstrap/ng-bootstrap';
import { VartableComponent } from './vartable/vartable.component';
import { PipelinejobComponent } from './pipelinejob/pipelinejob.component';


const routes: Routes = [
  {
    path: 'pipeline', component: PipelineComponent,
  }
];

@NgModule({
  declarations: [
    AppComponent,
    PipelineComponent,
    VartableComponent,
    PipelinejobComponent,
  ],
  imports: [
    BrowserModule,
    HttpClientModule,
    RouterModule.forRoot(routes),
    BrowserAnimationsModule,
    HttpClientModule,
    NgbModule
  ],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule { }
