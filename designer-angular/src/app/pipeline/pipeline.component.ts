import {interval, Observable} from 'rxjs';
import {Component, Injectable, OnInit, QueryList, ViewChildren} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {PipelineDocument} from '../pipelineTypes';
import {PipelinejobComponent} from '../pipelinejob/pipelinejob.component';


@Component({
  selector: 'app-pipeline',
  templateUrl: './pipeline.component.html',
  styleUrls: ['./pipeline.component.css']
})

@Injectable()
export class PipelineComponent implements OnInit {
  @ViewChildren(PipelinejobComponent) private childJobs: QueryList<PipelinejobComponent>;

  private timer: Observable<number>;
  pipeline: PipelineDocument;

  constructor(private http: HttpClient) {
    this.pollPipeline();
  }

  getJobComponent(name: string): PipelinejobComponent {
    console.log(this.childJobs);
    return null;
    /*
    for (const job of this.childJobs) {
      if (job.job != null) {
        if (job.job.name === name) {
          console.log('find ' + name);
          return job;
        }
      }
    }
    return null;*/
  }

  pollPipeline(): void {
    const resp = this.http.get('/api/pipeline', {observe: 'body', responseType: 'json'});
    resp.subscribe((data: PipelineDocument) => {
      this.pipeline = data;
      }
    );
  }

  ngOnInit(): void {
    this.timer = interval(2000);
    this.timer.subscribe(n => {
      this.pollPipeline();
    });
  }

}
