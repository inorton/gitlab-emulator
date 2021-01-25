import {interval, Observable} from 'rxjs';
import {Component, OnInit, ViewChild, AfterViewChecked, ElementRef, Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';

export interface PipelineJob {
  name: string;
  source_file: string;
  extends: string[];
  stage: string;
  needs: string[];
}


export interface PipelineDocument {
  filename: string;
  stages: string[];
  jobs: PipelineJob[];
  variables: Map<string, string>;
}

@Component({
  selector: 'app-pipeline',
  templateUrl: './pipeline.component.html',
  styleUrls: ['./pipeline.component.css']
})
@Injectable()
export class PipelineComponent implements OnInit {

  private timer: Observable<number>;
  pipeline: PipelineDocument;

  constructor(private http: HttpClient) {
    this.pollPipeline();
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
