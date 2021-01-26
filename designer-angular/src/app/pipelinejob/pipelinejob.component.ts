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

  active = false;

  constructor() {
  }

  ngOnInit(): void {
  }

  activate(): void {
    this.active = true;
    if (this.job != null) {
      for (const need of this.job.needs) {
        const comp = this.pipeline.getJobComponent(this.job.name);
        if (comp != null) {
         // comp.activate();
        }
      }
    }
  }

  deactivate(): void {
    this.active = false;
  }

}
