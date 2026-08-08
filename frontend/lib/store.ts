import {create} from 'zustand';import {NoorEvent,MemoryNode} from './types';
type State={events:NoorEvent[];memories:MemoryNode[];status:string;push:(e:NoorEvent)=>void;setMemories:(m:MemoryNode[])=>void};
export const useNoorStore=create<State>((set)=>({events:[],memories:[],status:'idle',push:(e)=>set((s)=>({events:[e,...s.events].slice(0,200),status:e.type.includes('error')?'error':e.type.includes('task')?'executing':s.status,memories:e.type==='memory.created'?[e.payload as MemoryNode,...s.memories]:s.memories})),setMemories:(m)=>set({memories:m})}));
