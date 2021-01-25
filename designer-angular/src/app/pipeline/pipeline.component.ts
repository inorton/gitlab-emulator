import {interval, Observable} from 'rxjs';
import {Component, Injectable, OnInit} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {PipelineDocument} from '../pipelineTypes';


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
