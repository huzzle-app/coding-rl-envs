function topoSort(nodes, edges) {
  const incoming = new Map(nodes.map((node) => [node, 0]));
  const graph = new Map(nodes.map((node) => [node, []]));

  for (const [source, target] of edges || []) {
    if (!graph.has(source)) graph.set(source, []);
    if (!incoming.has(source)) incoming.set(source, 0);
    if (!incoming.has(target)) incoming.set(target, 0);
    graph.get(source).push(target);
    incoming.set(target, incoming.get(target) + 1);
  }

  
  const queue = [...incoming.entries()].filter(([, deg]) => deg === 0).map(([node]) => node);
  const order = [];

  while (queue.length > 0) {
    const node = queue.shift();
    order.push(node);
    for (const neighbor of graph.get(node) || []) {
      incoming.set(neighbor, incoming.get(neighbor) - 1);
      
      if (incoming.get(neighbor) <= 0) {
        queue.push(neighbor);
        
      }
    }
  }

  if (order.length !== incoming.size) {
    throw new Error('dependency cycle detected');
  }
  return order;
}

module.exports = { topoSort };
