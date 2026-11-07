import {useCallback,useEffect,useRef,useState} from 'react';
export function useLiveLocation(){
  const [location,setLocation]=useState(null);
  const [status,setStatus]=useState('idle');
  const [error,setError]=useState('');
  const watch=useRef(null);
  const stop=useCallback(()=>{if(watch.current!==null&&navigator.geolocation){navigator.geolocation.clearWatch(watch.current);watch.current=null;setStatus('paused')}},[]);
  const start=useCallback(()=>{
    if(!navigator.geolocation){setError('This browser does not support location services.');setStatus('error');return}
    if(!window.isSecureContext){setError('Location tracking requires HTTPS or localhost.');setStatus('error');return}
    stop();setStatus('requesting');setError('');
    watch.current=navigator.geolocation.watchPosition(
      p=>{setLocation({lat:p.coords.latitude,lng:p.coords.longitude,accuracy:p.coords.accuracy,timestamp:p.timestamp,kind:'gps'});setStatus('tracking')},
      e=>{setError(e.code===1?'Location permission denied. You can use the demo start location.':e.message);setStatus('error')},
      {enableHighAccuracy:true,maximumAge:3000,timeout:15000});
  },[stop]);
  useEffect(()=>()=>{if(watch.current!==null)navigator.geolocation.clearWatch(watch.current)},[]);
  const useDemo=useCallback(()=>{stop();setLocation({lat:32.87965,lng:-117.23758,accuracy:null,kind:'demo'});setStatus('demo');setError('')},[stop]);
  return {location,status,error,start,stop,useDemo};
}
