import {Component, Input, OnInit} from '@angular/core';
import {PipelineDocument, PipelineJob} from '../pipelineTypes';
import {PipelineComponent} from "../pipeline/pipeline.component";


@Component({
  selector: 'app-pipelinejob',
  templateUrl: './pipelinejob.component.html',
  styleUrls: ['./pipelinejob.component.css']
})
export class PipelinejobComponent implements OnInit {

  @Input() job: PipelineJob;
  @Input() pipeline: PipelineComponent;

  active: boolean;

  constructor() {
  }

  ngOnInit(): void {
    this.deactivate();
  }

  activate(): void {
    this.active = true;
  }

  deactivate(): void {
    this.active = false;
  }

}
