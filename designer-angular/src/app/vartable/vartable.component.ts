import {Component, Input, OnInit} from '@angular/core';

@Component({
  selector: 'app-vartable',
  templateUrl: './vartable.component.html',
  styleUrls: ['./vartable.component.css']
})
export class VartableComponent implements OnInit {

  @Input() variables: Map<string, string>;
  @Input() buttonText: string;

  public isCollapsed = true;

  constructor() { }

  ngOnInit(): void {
  }

}
